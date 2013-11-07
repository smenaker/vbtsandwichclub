#!/usr/bin/env python2.5

__author__ = 'Kevin Le'

import decimal
import wsgiref.handlers
import os
import datetime

from google.appengine.api import users
from google.appengine.api import mail
from google.appengine.ext import webapp
from google.appengine.ext import db
from google.appengine.ext.webapp import template


class User(db.Model):
    username = db.StringProperty(required=True)
    fullname = db.StringProperty(required=True)
    password = db.StringProperty(required=True)
    monies = db.FloatProperty(required=True)
    receipt = db.BooleanProperty()

class Transaction(db.Model):
    buyer = db.StringProperty(required=True)
    date = db.DateTimeProperty(auto_now_add=True)
    items = db.StringListProperty()
    other = db.FloatProperty()
    total = db.FloatProperty()

class TransactionWrapper():
    def __init__(self,transaction):
        self.date = str(transaction.date.replace(tzinfo=UTC()).astimezone(Pacific_tzinfo()))[:-13]
        self.total = format_money(transaction.total)
    
class Item(db.Model):
    name = db.StringProperty(required=True)
    category = db.StringProperty()
    price = db.FloatProperty()

class Backup(db.Model):
    account = db.StringProperty(required=True)
    date = db.DateTimeProperty(auto_now_add=True)

fetch_matching_users = User.gql("WHERE username=:1",'rebind')

fetch_backup_info = Backup.gql("WHERE account=:1 ORDER BY date DESC",'voicebox')

fetch_user_transactions = Transaction.gql("WHERE buyer=:1 ORDER BY date DESC",'rebind')

voicebox_ip = '67.139.99.210'
voicebox_ip2 = '50.46.123.240'
#voicebox_ip = '64.122.170.170'
#voicebox_ip = '64.122.170.174'
#For testing purposes, comment out the line above and uncomment line below.
#voicebox_ip = '127.0.0.1'

class MainPage(webapp.RequestHandler):
    """Main Page View"""
    def get(self):
        path = os.path.join(os.path.dirname(__file__), 'index.html')
        self.response.out.write(template.render(path, PrepTemplate(self)))

class CreateUser(webapp.RequestHandler):
    """Called from the admin console to create a user"""
    def post(self):
        username = self.request.get('username').strip()
        global fetch_matching_users
        fetch_matching_users.bind(username)
        # check to see if there are any users with that username already
        usermatch = None
        for user in fetch_matching_users:
            usermatch = user
        if usermatch:
            self.redirect('error/userexists')
            return
        else:
            newuser = User(username=username,
                           fullname=username,
                           password='password',
                           monies=0.0,
                           receipt=False)
            newuser.put()
            template_values = {
                    'user':newuser,
                    }
            path = os.path.join(os.path.dirname(__file__),'edituser.html')
            self.response.out.write(template.render(path,PrepTemplate(self,template_values)))

class History(webapp.RequestHandler):
    """Encapsulates logic to view transaction history from admin or user view"""
    def post(self):
        username = self.request.get('username').strip()
        admin = users.is_current_user_admin()
        #legacy code for password support
        #if not admin:
            #password = self.request.get('password')
        global fetch_matching_users
        fetch_matching_users.bind(username)
        if fetch_matching_users.count() == 0:
            self.redirect('error/usernotexists') 
        #elif not admin and password != fetch_matching_users[0].password:
            #self.redirect('error/password') 
        else:
            DisplayUserHistory(self,fetch_matching_users[0], False)

class Pay(webapp.RequestHandler):
    """Called from the index for paying meals"""
    def post(self):
        try:
            payment = float(self.request.get('payment'))
            username = self.request.get('username').strip()
            global fetch_matching_users
            fetch_matching_users.bind(username)
            #password = self.request.get('password')
            if str(self.request.remote_addr) != voicebox_ip and str(self.request.remote_addr) != voicebox_ip2:
                self.redirect('error/badip')
                return
            elif payment < 0:
                self.redirect('error/negative')
                return
            elif (int(payment * 100)) % 5 > 0:
                self.redirect('error/increments')
                return
            elif fetch_matching_users.count() == 0:
                self.redirect('error/usernotexists')
                return
            #elif password != fetch_matching_users[0].password:
            #    self.redirect('error/password')
            #    return
            lasttransaction = GetLastTransaction(fetch_matching_users[0])
            if lasttransaction:
                # check for possible overcharge caused by hitting the pay button
                # multiple times
                delta = datetime.datetime.now() - lasttransaction.date
                if delta.seconds < 2:
                    #TODO(kevinl): print out message notifying possible accidental overcharge.
                    DisplayUserHistory(self, fetch_matching_users[0]) 
                    return
            newtransaction = Transaction(buyer=username,other=payment,total=-payment)
            if payment:
                newtransaction.put()
                for user in fetch_matching_users:
                    user.monies -= payment
                    user.put()
                    #if user.receipt:
                    SendReceipt(user,newtransaction)
            DisplayUserHistory(self,fetch_matching_users[0])
        except ValueError:
            self.redirect('error/float')

class ManageUsers(webapp.RequestHandler):
    """Main page of the admin console"""
    def get(self):
        global fetch_backup_info
        # Create a backup if there are no backups
        if fetch_backup_info.count() == 0:
            CreateBackup()
        else:
            # create a backup if a backup has not been made in less than a day
            timediff = datetime.datetime.now() - fetch_backup_info[0].date
            if timediff.days > 0:
                CreateBackup()

        if users.is_current_user_admin():
            # Generate a list of all individuals and their balances
            userquery = User.all().order('username')
            total = 0
            for user in userquery:
                total += user.monies 
            template_values = {
                    'users':userquery,
                    'total':total
                    }
            path = os.path.join(os.path.dirname(__file__), 'manageusers.html')
            self.response.out.write(template.render(path,PrepTemplate(self,template_values)))
        else:
            self.redirect('/')
    def post(self):
        username = self.request.get('username').strip()
        global fetch_matching_users
        fetch_matching_users.bind(username)
        usermatch = None
        for user in fetch_matching_users:
            usermatch = user
        if usermatch:
            template_values = {
                    'user':usermatch,
                    }
            path = os.path.join(os.path.dirname(__file__),'edituser.html')
            self.response.out.write(template.render(path,PrepTemplate(self,template_values)))
        else:
            self.redirect('error/usernotexists')

class Deposit(webapp.RequestHandler):
    """Called from the admin page to deposit money into an account"""
    def post(self):
        if users.is_current_user_admin():
            username = self.request.get('username').strip()
            global fetch_matching_users
            fetch_matching_users.bind(username)
            firstmatch = fetch_matching_users[0]
            try:
                deposit = float(self.request.get('addamount'))
            except ValueError:
                self.redirect('error/float')
                return
            if deposit < 0:
                self.redirect('error/negative')
                return
            firstmatch.monies += deposit
            firstmatch.put()
            newdeposit = Transaction(buyer=username,total=deposit)
            newdeposit.put()
            #if firstmatch.receipt:
            SendReceipt(firstmatch,newdeposit)
            DisplayUserHistory(self,firstmatch,False)
            return
        else:
            self.redirect('/')


class EditUser(webapp.RequestHandler):
    """Handles the admin function to edit a user"""
    def post(self):
        current_user = users.get_current_user()
        if current_user and users.is_current_user_admin():
            remove = self.request.get('remove')
            username = self.request.get('username').strip()
            matching = User.gql("WHERE username=:1",username)
            firstmatch = matching[0]
            if remove:  
                firstmatch.delete()
                self.redirect('/manageusers')
                return
            else:
                try:
                    fullname = self.request.get('fullname')
                    password = self.request.get('password')
                    setamount = float(self.request.get('setamount'))
                    
                    firstmatch.fullname = fullname
                    firstmatch.password = password
                    firstmatch.monies = setamount

                    firstmatch.put()
                    
                    self.redirect('/manageusers')
                    return
                except ValueError:
                    self.redirect('error/float')
                    return
        else:
            self.redirect('/')

class ChangePassword(webapp.RequestHandler):
    """Handles password changing functionality"""
    def post(self):
        username = self.request.get('username').strip()
        oldpassword = self.request.get('oldpassword')
        newpassword1 = self.request.get('newpassword1')
        newpassword2 = self.request.get('newpassword2')

        global fetch_matching_users
        fetch_matching_users.bind(username)
        if fetch_matching_users.count() == 0:
            self.redirect('error/usernotexists')
            return
        user = None
        for u in fetch_matching_users:
            user = u
        if oldpassword != user.password:
            self.redirect('error/password')
            return
        if newpassword1 != newpassword2:
            self.redirect('error/newpassword')
            return
        user.password = newpassword1
        user.put()
        self.redirect('success/passwordchanged')

class Static(webapp.RequestHandler):
    """Handles static page requests"""
    def get(self,request):
        if request == 'about':
            page = 'about.html'
        elif request == 'development':
            page = 'development.html'
        elif request == 'receipt':
            page = 'receipt.html'
        elif request == 'getuserhistory':
            page = 'getuserhistory.html'
        #elif request == 'changepassword':
            #page = 'changepassword.html'
        else:
            self.redirect('error/nopage')
            return
        path = os.path.join(os.path.dirname(__file__),page)
        self.response.out.write(template.render(path,PrepTemplate(self)))
class Success(webapp.RequestHandler):
    """Handles success messages"""
    def get(self,success):
        if success == 'passwordchanged':
            message = 'Password changed'
        elif success == 'receiptunsubscribed':
            message = 'You will no longer receive receipts'
        elif success == 'receiptsubscribed':
            message = 'You will begin receiving receipts'
        else:
            message = 'Success!'
        template_values = {
                'message':message
                }
        path = os.path.join(os.path.dirname(__file__),'submit_success.html')
        self.response.out.write(template.render(path,PrepTemplate(self,template_values)))
class Error(webapp.RequestHandler):
    """Handles error messages"""
    def get(self,error):
        if error == 'password':
            message = 'Incorrect password'
        elif error == 'badip':
            message = 'Sandwich Club is only usable on Voicebox properties.' + self.request.remote_addr
        elif error == 'float':
            message = 'Only floating point values accepted'
        elif error == 'increments':
            message = 'Payments are only accepted in 5 cent increments'
        elif error == 'negative':
            message = 'Only non-negative values accepted'
        elif error == 'newpassword':
            message = 'New passwords do not match'
        elif error == 'oldtransaction':
            message = 'The transaction you are trying to reverse is more than a day old'
        elif error == 'transactionnotexists':
            message = 'No transactions exist for this user.'
        elif error == 'usernotexists':
            message = 'This username does not exist yet'
        elif error == 'userexists':
            message = 'This username already exists'
        elif error == 'nopage':
            message = 'This static page does not exist'
        else:
            message = 'UNDEFINED ERROR. POSSIBLY RELATED TO SMOOTH JAZZ.'
        template_values = {
                'message':message,
                'redirect':True,
                }
        path = os.path.join(os.path.dirname(__file__),'submit_error.html')
        self.response.out.write(template.render(path,PrepTemplate(self,template_values)))
class Pacific_tzinfo(datetime.tzinfo):
    """Implementation of the Pacific timezone."""
    def utcoffset(self, dt):
        return datetime.timedelta(hours=-8) + self.dst(dt)
    
    def _FirstSunday(self, dt):
        """First Sunday on or after dt."""
        return dt + datetime.timedelta(days=(6-dt.weekday()))
    def dst(self, dt):
        # 2 am on the second Sunday in March
        dst_start = self._FirstSunday(datetime.datetime(dt.year, 3, 8, 2))
        # 1 am on the first Sunday in November
        dst_end = self._FirstSunday(datetime.datetime(dt.year, 11, 1, 1))
        if dst_start <= dt.replace(tzinfo=None) < dst_end:
            return datetime.timedelta(hours=1)
        else:
            return datetime.timedelta(hours=0)

    def tzname(self, dt):
        if self.dst(dt) == datetime.timedelta(hours=0):
            return "PST"
        else:
            return "PDT"

class UTC(datetime.tzinfo):
    """Implementation of the UTC (GMT) timezone."""
    def utcoffset(self, dt):
        return datetime.timedelta(0)
    def tzname(self, dt):
        return "UTC"
    def dst(self, dt):
        return datetime.timedelta(0)

class Receipt(webapp.RequestHandler):
    """Request handler for getting the subscription to receipts
    info of a user"""
    def post(self):
        username = self.request.get('username').strip()
        global fetch_matching_users
        fetch_matching_users.bind(username)
        if fetch_matching_users.count() == 0:
            self.redirect('error/usernotexists')
            return
        template_values = {
                'username': username,
                'receipt': fetch_matching_users[0].receipt
                }
        path = os.path.join(os.path.dirname(__file__),'subscribe.html')
        self.response.out.write(template.render(path,PrepTemplate(self,template_values)))
class Subscribe(webapp.RequestHandler):
    """Request handler for subscribing and unsubscribing to 
    email receipts"""
    def post(self):
        username = self.request.get('username').strip()
        receipt = self.request.get('receipt')
        global fetch_matching_users 
        fetch_matching_users.bind(username)
        if fetch_matching_users.count() == 0:
            self.redirect('error/usernotexists')
            return
        user = fetch_matching_users[0]
        if receipt == 'check':
            user.receipt = True
        else:
            user.receipt = False
        user.put()
        if receipt:
            self.redirect('success/receiptsubscribed')
        else:
            self.redirect('success/receiptunsubscribed')

class Reverse(webapp.RequestHandler):
    """Request handler for reversal of transactions."""
    def post(self):
        username = self.request.get('username').strip()
        global fetch_matching_users
        fetch_matching_users.bind(username)
        if fetch_matching_users.count() == 0:
            self.redirect('error/usernotexists')
            return
        user = fetch_matching_users[0]
        transaction = GetLastTransaction(user)
        if transaction:
            # check to make sure the transaction is less than a day old.
            timedelta = datetime.datetime.now() - transaction.date
            if timedelta.days == 0:
                user.monies -= transaction.total
                user.put()
                transaction.delete()
                DisplayUserHistory(self,user,False)
                return
            else:
                self.redirect('error/oldtransaction')

def GetLastTransaction(user):
    """Returns the the most recent transaction of a user.

    Args:
        user: a user object (db.Model) whose most recent
            transaction you are trying to obtain.
    
    Returns:
        a Transaction object, representing the user's latest
            transaction
        or
        None, if the user has no transactions
        
    """
    global fetch_user_transactions
    fetch_user_transactions.bind(user.username)
    if fetch_user_transactions.count() != 0:
        return fetch_user_transactions[0]
    else:
        return None
def PrepTemplate(request_handler,template_values={}):
    """Called on a set of template values to append to it information
    about whether or not the user is logged in, and whether or not the
    user is an admin so that the appropriate sidebar items are displayed
    properly.
    
    Args:
        request_handler: A webapp.RequestHandler object which needs the
            updated template values.
        template_values: A dictionary with the request handlers own key
            value pairs defined. If one is not provided, an empty 
            dictionary is used.
            
    Returns:
        A dictionary whose key value pairs for 'url','url_linktext', and
        'admin' are set.
    """
    user = users.get_current_user()
    admin = False
    if users.get_current_user():
        url = users.create_logout_url(request_handler.request.uri)
        url_linktext = 'Logout'
        if users.is_current_user_admin():
            admin = True
    else:
        url = users.create_login_url(request_handler.request.uri)
        url_linktext = 'Admin Login'
    template_values['url'] = url
    template_values['url_linktext'] = url_linktext
    template_values['admin'] = admin
    return template_values

def DisplayUserHistory(request_handler,user,auto_redirect=True):
    """Called from request handlers to display a user's history.
    
    Args:
        request_handler: A webapp.RequestHandler object which sends the
            history display request.
        user: The user object (db.Model) whose history you are trying to
            display.
        auto_redirect: Set this to False if you do not want the history
            page to autoredirect to home in 5 seconds.

    Returns:
        None
    """
    global fetch_user_transactions, voicebox_ip
    if str(request_handler.request.remote_addr) != voicebox_ip:
        request_handler.redirect('error/badip')
    fetch_user_transactions.bind(user.username)
    # wraps the transactions up in string fields
    transactions_wrapped = []
    for transaction in fetch_user_transactions:
        transactions_wrapped.append(TransactionWrapper(transaction))
    # check if reversible transactions are available
    if fetch_user_transactions.count() != 0:
        timedelta  = datetime.datetime.now() - fetch_user_transactions[0].date
        if timedelta.days == 0:
            reversible = True
        else:
            reversible = False
    else:
        reversible = False
    template_values = {
            'username':user.username,
            'balance':user.monies,
            'transactions':transactions_wrapped,
            'redirect':auto_redirect,
            'reversible':reversible,
            }
    path = os.path.join(os.path.dirname(__file__), 'history.html')
    request_handler.response.out.write(template.render(path, PrepTemplate(request_handler,template_values)))

def CreateBackup():
    """Generates a backup email containing all usernames, fullnames, and balances
    (no passwords) to Tyler Sellon. A copy of the email exists in the sender
    email voiceboxsandwichclub@gmail.com.
    
    Returns:
        None
    """
    global fetch_backup_info
    for backup in fetch_backup_info:
        backup.delete()
    newbackup = Backup(account='voicebox')
    newbackup.put()

    sender_address = 'voiceboxsandwichclub@gmail.com'
    user_address = 'tylers@voicebox.com'
    subject = 'Latest Sandwich Club Data'
    body = ''
    # Create a list of all the users, their names, and their balances.
    for user in User.all().order('username'):
        body += '%s\t%s\t%f\n'%(user.username,user.fullname,user.monies)
    mail.send_mail(sender_address,user_address,subject,body)

def SendReceipt(user,transaction):
    """Send a receipt to a user
    
    Args:
        user: A user object (db.Model) who you are going to mail.
        transaction: A transaction object (db.Model) which you are sending a
            notification of.
            
    Returns: 
        None
    """
    transactionpst = transaction.date.replace(tzinfo=UTC()).astimezone(Pacific_tzinfo())
    transactiondate = transactionpst.date()
    transactiontime = transactionpst.time()
    if transaction.total > 0:
        delta = 'Deposit'
    if transaction.total <= 0:
        delta = 'Purchase'
    sender_address = 'voiceboxsandwichclub@gmail.com'
    user_address = '%s@voicebox.com' % user.username
	# take a substring of the transaction time that excludes microseconds.
    subject = 'Sandwich Club %s %s @ %s' % (delta,str(transactiondate),str(transactiontime)[:8])
    total = format_money(transaction.total)
    monies = format_money(user.monies)
    body = 'Thank you, %s, for using the <a href="http://voicebox-sandwich.appspot.com/">Sandwich Club</a>!\n\nUsername: %s\nTransaction: %s\nNew Balance: %s' % (user.fullname,user.username,total,monies)
    if user.username != 'voicebox':
        mail.send_mail(sender_address,user_address,subject,body)

def format_money(money):
    """Formats floating point money values into a more readable $x.xx form.
    
    Args:
        money: A floating point value representing a dollar amount.
        
    Returns:
        A string of the form '$X.XX' or '-$X.XX' depending on the sign.
    """
    moneystr = str(money)
    # case where there is no decimal
    if moneystr.find('.') == -1:
        moneystr = '%s.00' % (moneystr)
    moneysplit = moneystr.split('.')
    # joins all the digits before the decimal place with 2 digits after the
    # decimal place by a '.'
    money_mat = '.'.join([moneysplit[0],moneysplit[1][:2].ljust(2,'0')])
    if money_mat.find('-') == -1:
        return '$%s' % money_mat
    else:
        return '-$%s' % money_mat.lstrip('-')

def main():
    """Redirects page requests to the appropriate RequestHandler"""
    application = webapp.WSGIApplication([
                                        ('/', MainPage),
                                        #('/changepassword',ChangePassword),
                                        ('/receipt',Receipt),
                                        ('/createuser',CreateUser),
                                        ('/deposit',Deposit),
                                        ('/edituser',EditUser),
                                        ('/error/(.*)',Error),
                                        ('/history', History),
                                        ('/manageusers',ManageUsers),
                                        ('/pay', Pay),
                                        ('/reverse',Reverse),
                                        ('/static/(.*)',Static),
                                        ('/subscribe',Subscribe),
                                        ('/success/(.*)',Success),
                                        ],
                                        debug=True)
    wsgiref.handlers.CGIHandler().run(application)
if __name__ == "__main__":
    main()

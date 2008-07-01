#!/usr/bin/env python2.5
#Kevin Le

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

class Transaction(db.Model):
    buyer = db.StringProperty(required=True)
    date = db.DateTimeProperty(auto_now_add=True)
    items = db.StringListProperty()
    other = db.FloatProperty()
    total = db.FloatProperty()
    
class Item(db.Model):
    name = db.StringProperty(required=True)
    category = db.StringProperty()
    price = db.FloatProperty()

class Backup(db.Model):
    account = db.StringProperty(required=True)
    date = db.DateTimeProperty(auto_now_add=True)

fetch_matching_users = User.gql("WHERE username=:1",'rebind')

fetch_backup_info = Backup.gql("WHERE account=:1 ORDER BY date DESC",'voicebox')

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
                           monies=0.0)
            newuser.put()
            template_values = {
            'user':newuser,
            }
            path = os.path.join(os.path.dirname(__file__),'edituser.html')
            self.response.out.write(template.render(path,PrepTemplate(self,template_values)))

class History(webapp.RequestHandler):
    """Encapsulates logic to view transaction history from admin or user view"""
    def get(self):
        path = os.path.join(os.path.dirname(__file__), 'getuserhistory.html') 
        self.response.out.write(template.render(path, PrepTemplate(self)))
    def post(self):
        username = self.request.get('username').strip()
        admin = users.is_current_user_admin()
        if not admin:
            password = self.request.get('password')
        global fetch_matching_users
        fetch_matching_users.bind(username)
        if fetch_matching_users.count() == 0:
            self.redirect('error/usernotexists') 
        elif not admin and password != fetch_matching_users[0].password:
            self.redirect('error/password') 
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
            password = self.request.get('password')
            if payment < 0:
                self.redirect('error/negative')
                return
            elif fetch_matching_users.count() == 0:
                self.redirect('error/usernotexists')
                return
            elif password != fetch_matching_users[0].password:
                self.redirect('error/password')
                return
            newtransaction = Transaction(buyer=username,other=payment,total=-payment)
            if payment:
                newtransaction.put()
                for user in fetch_matching_users:
                    user.monies -= payment
                    user.put()
            DisplayUserHistory(self,fetch_matching_users[0])
        except ValueError:
            self.redirect('error/float')

class ManageUsers(webapp.RequestHandler):
    """Main page of the admin console"""
    def get(self):
        global fetch_backup_info
        if fetch_backup_info.count() == 0:
            CreateBackup()
        else:
            timediff = datetime.datetime.now() - fetch_backup_info[0].date
            if timediff.days > 0:
                CreateBackup()

        if users.is_current_user_admin():
            userquery = User.all().order('username')
            template_values = {
            'users':userquery
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
    def get(self): 
        path = os.path.join(os.path.dirname(__file__),'changepassword.html')
        self.response.out.write(template.render(path,PrepTemplate(self)))
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
        template_values = {
        'message':'Password changed'
        }
        path = os.path.join(os.path.dirname(__file__),'submit_success.html')
        self.response.out.write(template.render(path,PrepTemplate(self,template_values)))

class Static(webapp.RequestHandler):
    """Handles static page requests"""
    def get(self,request):
        if request == 'about':
            page = 'about.html'
        elif request == 'development':
            page = 'development.html'
        else:
            self.redirect('/error/nopage')
            return
        path = os.path.join(os.path.dirname(__file__),page)
        self.response.out.write(template.render(path,PrepTemplate(self)))
class Error(webapp.RequestHandler):
    """Handles error messages"""
    def get(self,error):
        if error == 'password':
            message = 'Incorrect password'
        elif error == 'float':
            message = 'Only floating point values accepted'
        elif error == 'negative':
            message = 'Only non-negative values accepted'
        elif error == 'newpassword':
            message = 'New passwords do not match'
        elif error == 'usernotexists':
            message = 'This username does not exist yet'
        elif error == 'userexists':
            message = 'This username already exists'
        elif error == 'nopage':
            message = 'This static page does not exist'
        else:
            message = 'UNDEFINED ERROR. POSSIBLY RELATED TO SMOOTH JAZZ.'
        template_values = {
        'message':message
        }
        path = os.path.join(os.path.dirname(__file__),'submit_error.html')
        self.response.out.write(template.render(path,PrepTemplate(self,template_values)))

def PrepTemplate(request_handler,template_values={}):
    """Called on a set of template values to append to it information
    about whether or not the user is logged in, and whether or not the
    user is an admin so that the appropriate sidebar items are displayed
    properly."""
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
    """This function is called from a webapp.RequestHandler function, 
    which passes itself, a db.Model User and a flag indicating whether
    the page should redirect itself to the main page"""
    transactions = Transaction.gql("WHERE buyer=:1 ORDER BY date DESC",user.username)
    template_values = {
    'username':user.username,
    'balance':user.monies,
    'transactions':transactions,
    'redirect':auto_redirect,
    }
    path = os.path.join(os.path.dirname(__file__), 'history.html')
    request_handler.response.out.write(template.render(path, PrepTemplate(request_handler,template_values)))

def CreateBackup():
    """Generates a backup email containing all usernames, fullnames, and balances
    (no passwords) to Tyler Sellon. A copy of the email exists in the sender
    email voiceboxsandwichclub@gmail.com."""
    global fetch_backup_info
    for backup in fetch_backup_info:
        backup.delete()
    newbackup = Backup(account='voicebox')
    newbackup.put()

    sender_address = 'voiceboxsandwichclub@gmail.com'
    user_address = 'tylers@voicebox.com'
    subject = 'Latest Sandwich Club Data'
    body = ''
    for user in User.all().order('username'):
        body += '%s\t%s\t%f\n'%(user.username,user.fullname,user.monies)
    mail.send_mail(sender_address,user_address,subject,body)

def main():
    """Redirects page requests to the appropriate webapp.RequestHandler"""
    application = webapp.WSGIApplication([
                                        ('/', MainPage),
                                        ('/changepassword',ChangePassword),
                                        ('/createuser',CreateUser),
                                        ('/deposit',Deposit),
                                        ('/edituser',EditUser),
                                        ('/error/(.*)',Error),
                                        ('/history', History),
                                        ('/manageusers',ManageUsers),
                                        ('/pay', Pay),
                                        ('/static/(.*)',Static),
                                        ],
                                        debug=True)
    wsgiref.handlers.CGIHandler().run(application)
if __name__ == "__main__":
    main()

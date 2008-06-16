#!/usr/bin/env python2.5
#Kevin Le

import decimal
import wsgiref.handlers
import os

from google.appengine.api import users
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

class MainPage(webapp.RequestHandler):
    """Main Page View"""

    def get(self):
        user = users.get_current_user()
        admin = False
        if users.get_current_user():
            url = users.create_logout_url(self.request.uri)
            url_linktext = 'Logout'
            if users.is_current_user_admin():
                admin = True
        else:
            url = users.create_login_url(self.request.uri)
            url_linktext = 'Login'

        template_values = {
        'url': url,
        'url_linktext': url_linktext,
        'admin': admin,
        }
        path = os.path.join(os.path.dirname(__file__), 'index.html')
        self.response.out.write(template.render(path, template_values))
class CreateUser(webapp.RequestHandler):
    def post(self):
        username = self.request.get('username')
        match = User.gql("WHERE username=:1 LIMIT 1",username)
        usermatch = None
        for user in match:
            usermatch = user
        if usermatch:
            template_values = {
            'message':'Username %s already exists'%username,
            'admin':True if users.is_current_user_admin() else False
            }
            path = os.path.join(os.path.dirname(__file__),'submit_error.html')
            self.response.out.write(template.render(path,template_values))
            return
        else:
            newuser = User(username=username,
                           fullname=username,
                           password='password',
                           monies=0.0)
            newuser.put()
            template_values = {
            'user':newuser,
            'admin':True if users.is_current_user_admin() else False
            }
            path = os.path.join(os.path.dirname(__file__),'edituser.html')
            self.response.out.write(template.render(path,template_values))

class Recent(webapp.RequestHandler):
    def get(self):
        transactions = Transaction.gql("ORDER BY date DESC LIMIT 1")
        recentuser=''
        for transaction in transactions:
            recentuser = transaction.buyer
        recentuser_fetch = User.gql("WHERE username=:1 LIMIT 1",recentuser)
        recentuser_model = None
        for usermodel in recentuser_fetch:
            recentuser_model = usermodel
        
        recentuser_transactions = Transaction.gql("WHERE buyer=:1 ORDER BY date DESC",recentuser_model.username)
        template_values = {
        'username':recentuser_model.username,
        'balance':recentuser_model.monies,
        'transactions':recentuser_transactions,
        'admin':True if users.is_current_user_admin() else False
        }
        path = os.path.join(os.path.dirname(__file__), 'history.html')
        self.response.out.write(template.render(path, template_values))

class History(webapp.RequestHandler):

    def get(self):
        path = os.path.join(os.path.dirname(__file__), 'getuserhistory.html')
        template_values = {
        'admin':True if users.is_current_user_admin() else False
        }
        self.response.out.write(template.render(path, template_values))
    def post(self):
        username = self.request.get('username')
        password = self.request.get('password')
        matchingusers = User.gql("WHERE username=:1",username)
        if matchingusers.count() == 0:
            template_values = {
            'message':'Username not found',
            'admin':True if users.is_current_user_admin() else False
            }
            path = os.path.join(os.path.dirname(__file__), 'submit_error.html')
            self.response.out.write(template.render(path,template_values))
        elif password != matchingusers[0].password:
            template_values = {
            'message':'Incorrect password',
            'admin':True if users.is_current_user_admin() else False
            }
            path = os.path.join(os.path.dirname(__file__), 'submit_error.html')
            self.response.out.write(template.render(path,template_values))
        else:
            self.GetUserHistory(matchingusers[0])
    def GetUserHistory(self,user):
        transactions = Transaction.gql("WHERE buyer=:1 ORDER BY date DESC",user.username)

        template_values = {
        'username':user.username,
        'balance':user.monies,
        'transactions':transactions,
        'admin':True if users.is_current_user_admin() else False
        }
        path = os.path.join(os.path.dirname(__file__), 'history.html')
        self.response.out.write(template.render(path, template_values))


class Pay(webapp.RequestHandler):

    def post(self):
        try:
            payment = float(self.request.get('payment'))
            username = self.request.get('username')
            matchingusers = User.gql("WHERE username=:1",username)
            password = self.request.get('password')
            if payment < 0:
                template_values = {
                'message':'Please enter a non-negative transaction',
                'admin':True if users.is_current_user_admin() else False
                }
                path = os.path.join(os.path.dirname(__file__), 'submit_error.html')
                self.response.out.write(template.render(path,template_values))
                return
            elif matchingusers.count() == 0:
                template_values = {
                'message':'Username not found',
                'admin':True if users.is_current_user_admin() else False
                }
                path = os.path.join(os.path.dirname(__file__), 'submit_error.html')
                self.response.out.write(template.render(path,template_values))
                return
            elif password != matchingusers[0].password:
                template_values = {
                'message':'Incorrect password',
                'admin':True if users.is_current_user_admin() else False
                }
                path = os.path.join(os.path.dirname(__file__), 'submit_error.html')
                self.response.out.write(template.render(path,template_values))
                return
            newtransaction = Transaction(buyer=username,other=payment,total=-payment)
            if payment:
                newtransaction.put()
                for user in matchingusers:
                    user.monies -= payment
                    user.put()
            self.redirect('/recent')
            #History.GetUserHistory(History(),matchingusers[0])
        except ValueError:
            template_values = {
            'message':'Please enter a floating point value in the amount fields.',
            'admin':True if users.is_current_user_admin() else False
            }
            path = os.path.join(os.path.dirname(__file__), 'submit_error.html')
            self.response.out.write(template.render(path,template_values))

class ManageUsers(webapp.RequestHandler):
    """Find a user to edit"""
    def get(self):
        current_user = users.get_current_user()
        if current_user and users.is_current_user_admin():
            userquery = User.all()
            template_values = {
            'users':userquery,
            'admin':True if users.is_current_user_admin() else False
            }
            path = os.path.join(os.path.dirname(__file__), 'manageusers.html')
            self.response.out.write(template.render(path,template_values))
        else:
            self.redirect('/')
    def post(self):
        username = self.request.get('username')
        match = User.gql("WHERE username=:1 LIMIT 1",username)
        usermatch = None
        for user in match:
            usermatch = user
        if usermatch:
            template_values = {
            'user':usermatch,
            'admin':True if users.is_current_user_admin() else False
            }
            path = os.path.join(os.path.dirname(__file__),'edituser.html')
            self.response.out.write(template.render(path,template_values))
        else:
            template_values = {
            'message':'Username %s does not exist yet'%username,
            'admin':True if users.is_current_user_admin() else False
            }
            path = os.path.join(os.path.dirname(__file__),'submit_error.html')
            self.response.out.write(template.render(path,template_values))

class Deposit(webapp.RequestHandler):
    def post(self):
        if users.is_current_user_admin():
            username = self.request.get('username')
            matching = User.gql("WHERE username=:1",username)
            firstmatch = matching[0]
            try:
                deposit = float(self.request.get('addamount'))
            except ValueError:
                template_values = {
                'message':'Please enter a floating point value',
                'admin':True if users.is_current_user_admin() else False
                }
                path = os.path.join(os.path.dirname(__file__), 'submit_error.html')
                self.response.out.write(template.render(path,template_values))
                return
            if deposit < 0:
                template_values = {
                'message':'Please enter a non-negative value',
                'admin':True if users.is_current_user_admin() else False
                }
                path = os.path.join(os.path.dirname(__file__), 'submit_error.html')
                self.response.out.write(template.render(path,template_values))
                return
            firstmatch.monies += deposit
            firstmatch.put()
            newdeposit = Transaction(buyer=username,total=deposit)
            newdeposit.put()
            self.redirect('/recent')
            return
        else:
            self.redirect('/')


class EditUser(webapp.RequestHandler):
    """Edit a user"""
    def post(self):
        current_user = users.get_current_user()
        if current_user and users.is_current_user_admin():
            remove = self.request.get('remove')
            username = self.request.get('username')
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
                    template_values = {
                    'message':'Please enter a floating point value in the amount fields.',
                    'admin':True if users.is_current_user_admin() else False
                    }
                    path = os.path.join(os.path.dirname(__file__), 'submit_error.html')
                    self.response.out.write(template.render(path,template_values))
                    return
        else:
            self.redirect('/')

class ViewUserHistory(webapp.RequestHandler):
    def post(self):
        username = self.request.get('username')
        matchingusers = User.gql("WHERE username=:1",username)
        if matchingusers.count() == 0:
            template_values = {
            'message':'Username not found',
            'admin':True if users.is_current_user_admin() else False
            }
            path = os.path.join(os.path.dirname(__file__), 'submit_error.html')
            self.response.out.write(template.render(path,template_values))
        else:
            self.GetUserHistory(matchingusers[0])
    def GetUserHistory(self,user):
        transactions = Transaction.gql("WHERE buyer=:1 ORDER BY date DESC",user.username)

        template_values = {
        'username':user.username,
        'balance':user.monies,
        'transactions':transactions,
        'admin':True if users.is_current_user_admin() else False
        }
        path = os.path.join(os.path.dirname(__file__), 'history.html')
        self.response.out.write(template.render(path, template_values))
class ChangePassword(webapp.RequestHandler):
    def get(self):
        path = os.path.join(os.path.dirname(__file__),'changepassword.html')
        self.response.out.write(template.render(path,None))
    def post(self):
        username = self.request.get('username')
        oldpassword = self.request.get('oldpassword')
        newpassword1 = self.request.get('newpassword1')
        newpassword2 = self.request.get('newpassword2')

        matchingusers = User.gql("WHERE username=:1 LIMIT 1",username)
        if matchingusers.count() == 0:
            template_values = {
            'message':'Username not found',
            'admin':True if users.is_current_user_admin() else False
            }
            path = os.path.join(os.path.dirname(__file__),'submit_error.html')
            self.response.out.write(template.render(path,template_values))
            return
        user = None
        for u in matchingusers:
            user = u
        if oldpassword != user.password:
            template_values = {
            'message':'Incorrect password',
            'admin':True if users.is_current_user_admin() else False
            }
            path = os.path.join(os.path.dirname(__file__),'submit_error.html')
            self.response.out.write(template.render(path,template_values))
            return
        if newpassword1 != newpassword2:
            template_values = {
            'message':'New passwords do not match',
            'admin':True if users.is_current_user_admin() else False
            }
            path = os.path.join(os.path.dirname(__file__),'submit_error.html')
            self.response.out.write(template.render(path,template_values))
            return
        user.password = newpassword1
        user.put()
        template_values = {
        'message':'Password changed',
        'admin':True if users.is_current_user_admin() else False
        }
        path = os.path.join(os.path.dirname(__file__),'submit_success.html')
        self.response.out.write(template.render(path,template_values))



def main():
    application = webapp.WSGIApplication([('/', MainPage),
                                        ('/pay', Pay),
                                        ('/createuser',CreateUser),
                                        ('/viewuserhistory',ViewUserHistory),
                                        ('/changepassword',ChangePassword),
                                        ('/history', History),
                                        ('/recent', Recent),
                                        ('/deposit',Deposit),
                                        ('/manageusers',ManageUsers),
                                        ('/edituser',EditUser)],
                                        debug=True)
    wsgiref.handlers.CGIHandler().run(application)

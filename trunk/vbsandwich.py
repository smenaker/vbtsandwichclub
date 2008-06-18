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
        path = os.path.join(os.path.dirname(__file__), 'index.html')
        self.response.out.write(template.render(path, PrepTemplate(self)))

class CreateUser(webapp.RequestHandler):
    def post(self):
        username = self.request.get('username')
        match = User.gql("WHERE username=:1 LIMIT 1",username)
        usermatch = None
        for user in match:
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

    def get(self):
        path = os.path.join(os.path.dirname(__file__), 'getuserhistory.html') 
        self.response.out.write(template.render(path, PrepTemplate(self)))
    def post(self):
        username = self.request.get('username')
        password = self.request.get('password')
        matchingusers = User.gql("WHERE username=:1",username)
        if matchingusers.count() == 0:
            self.redirect('error/usernotexists') 
        elif password != matchingusers[0].password:
            self.redirect('error/password') 
        else:
            DisplayUserHistory(self,matchingusers[0])

class Pay(webapp.RequestHandler):

    def post(self):
        try:
            payment = float(self.request.get('payment'))
            username = self.request.get('username')
            matchingusers = User.gql("WHERE username=:1",username)
            password = self.request.get('password')
            if payment < 0:
                self.redirect('error/negative')
                return
            elif matchingusers.count() == 0:
                self.redirect('error/usernotexists')
                return
            elif password != matchingusers[0].password:
                self.redirect('error/password')
                return
            newtransaction = Transaction(buyer=username,other=payment,total=-payment)
            if payment:
                newtransaction.put()
                for user in matchingusers:
                    user.monies -= payment
                    user.put()
            DisplayUserHistory(self,matchingusers[0])
        except ValueError:
            self.redirect('error/float')

class ManageUsers(webapp.RequestHandler):
    """Find a user to edit"""
    def get(self):
        current_user = users.get_current_user()
        if current_user and users.is_current_user_admin():
            userquery = User.all().order('username')
            template_values = {
            'users':userquery
            }
            path = os.path.join(os.path.dirname(__file__), 'manageusers.html')
            self.response.out.write(template.render(path,PrepTemplate(self,template_values)))
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
            }
            path = os.path.join(os.path.dirname(__file__),'edituser.html')
            self.response.out.write(template.render(path,PrepTemplate(self,template_values)))
        else:
            self.redirect('error/usernotexists')

class Deposit(webapp.RequestHandler):
    def post(self):
        if users.is_current_user_admin():
            username = self.request.get('username')
            matching = User.gql("WHERE username=:1",username)
            firstmatch = matching[0]
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
            DisplayUserHistory(self,firstmatch)
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
                    self.redirect('error/float')
                    return
        else:
            self.redirect('/')

class ViewUserHistory(webapp.RequestHandler):
    def post(self):
        username = self.request.get('username')
        matchingusers = User.gql("WHERE username=:1",username)
        if matchingusers.count() == 0:
            self.redirect('error/usernotexists')
        else:
            DisplayUserHistory(self,matchingusers[0])

class ChangePassword(webapp.RequestHandler):
    def get(self): 
        path = os.path.join(os.path.dirname(__file__),'changepassword.html')
        self.response.out.write(template.render(path,PrepTemplate(self)))
    def post(self):
        username = self.request.get('username')
        oldpassword = self.request.get('oldpassword')
        newpassword1 = self.request.get('newpassword1')
        newpassword2 = self.request.get('newpassword2')

        matchingusers = User.gql("WHERE username=:1 LIMIT 1",username)
        if matchingusers.count() == 0:
            self.redirect('error/usernotexists')
            return
        user = None
        for u in matchingusers:
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

class About(webapp.RequestHandler):
    def get(self):
        path = os.path.join(os.path.dirname(__file__),'about.html')
        self.response.out.write(template.render(path,PrepTemplate(self)))
class Error(webapp.RequestHandler):
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
        else:
            message = 'UNDEFINED ERROR. POSSIBLY RELATED TO SMOOTH JAZZ.'
        template_values = {
        'message':message
        }
        path = os.path.join(os.path.dirname(__file__),'submit_error.html')
        self.response.out.write(template.render(path,PrepTemplate(self,template_values)))

def PrepTemplate(request_handler,template_values={}):
    user = users.get_current_user()
    admin = False
    if users.get_current_user():
        url = users.create_logout_url(request_handler.request.uri)
        url_linktext = 'Logout'
        if users.is_current_user_admin():
            admin = True
    else:
        url = users.create_login_url(request_handler.request.uri)
        url_linktext = 'Login'
    template_values['url'] = url
    template_values['url_linktext'] = url_linktext
    template_values['admin'] = admin
    return template_values

def DisplayUserHistory(request_handler,user):
    transactions = Transaction.gql("WHERE buyer=:1 ORDER BY date DESC",user.username)
    template_values = {
    'username':user.username,
    'balance':user.monies,
    'transactions':transactions
    }
    path = os.path.join(os.path.dirname(__file__), 'history.html')
    request_handler.response.out.write(template.render(path, PrepTemplate(request_handler,template_values)))

def main():
    application = webapp.WSGIApplication([('/', MainPage),
                                        ('/pay', Pay),
                                        ('/about',About),
                                        ('/createuser',CreateUser),
                                        ('/viewuserhistory',ViewUserHistory),
                                        ('/changepassword',ChangePassword),
                                        (r'/error/(.*)',Error),
                                        ('/history', History),
                                        ('/deposit',Deposit),
                                        ('/manageusers',ManageUsers),
                                        ('/edituser',EditUser)],
                                        debug=True)
    wsgiref.handlers.CGIHandler().run(application)

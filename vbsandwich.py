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
    price = db.FloatProperty()

def UpdateItem(name,newname=None,newprice=None):
    """Update an item in the database"""
    items = db.GqlQuery("SELECT * FROM Item WHERE name = :1",name)
    for item in items:
        if newname:
            item.name=newname
        if newprice:
            item.price=newprice
class ChangeModel(db.Model):
    user = db.UserProperty()
    input = db.IntegerProperty()
    date = db.DateTimeProperty(auto_now_add=True)

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

class Recent(webapp.RequestHandler):
    """Query Last 10 Requests"""

    def get(self):

        #collection
        collection = []
        #grab last 10 records from datastore
        query = ChangeModel.all().order('-date')
        records = query.fetch(limit=10)

        #formats decimal correctly
        for change in records:
            collection.append(decimal.Decimal(change.input)/100)

        template_values = {
        'inputs': collection,
        'records': records,
        }

        path = os.path.join(os.path.dirname(__file__), 'query.html')
        self.response.out.write(template.render(path,template_values))

class History(webapp.RequestHandler):

    def get(self):
        path = os.path.join(os.path.dirname(__file__), 'getuserhistory.html')
        self.response.out.write(template.render(path, None))
    def post(self):
        username = self.request.get('username')
        password = self.request.get('password')
        matchingusers = User.gql("WHERE username=:1",username)
        if matchingusers.count() == 0:
			template_values = {
			'message':'Username not found'
			}
			path = os.path.join(os.path.dirname(__file__), 'submit_error.html')
			self.response.out.write(template.render(path,template_values))
        elif password != matchingusers[0].password:
			template_values = {
			'message':'Incorrect password'
		    }
			path = os.path.join(os.path.dirname(__file__), 'submit_error.html')
			self.response.out.write(template.render(path,template_values))
        else:
            self.GetUserHistory(matchingusers[0])
    def GetUserHistory(self,user):
        transactions = Transaction.gql("WHERE buyer=:1",user.username)

        template_values = {
        'username':user.username,
        'balance':repr(user.monies)[:18],
        'transactions':transactions
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
				'message':'Please enter a non-negative transaction'
			    }
				path = os.path.join(os.path.dirname(__file__), 'submit_error.html')
				self.response.out.write(template.render(path,template_values))
            elif matchingusers.count() == 0:
				template_values = {
				'message':'Username not found'
			    }
				path = os.path.join(os.path.dirname(__file__), 'submit_error.html')
				self.response.out.write(template.render(path,template_values))
            elif password != matchingusers[0].password:
				template_values = {
				'message':'Incorrect password'
			    }
				path = os.path.join(os.path.dirname(__file__), 'submit_error.html')
				self.response.out.write(template.render(path,template_values))
            newtransaction = Transaction(buyer=username,other=payment,total=payment)
            if payment:
                newtransaction.put()
                matchingusers[0].monies -= payment
                matchingusers[0].put()
            #History.GetUserHistory(History(),matchingusers[0])
        except ValueError:
            ErrorHandler.write_error('Please enter a floating point value in the amount fields.')

class ManageUsers(webapp.RequestHandler):
    """Find a user to edit"""
    def get(self):
        current_user = users.get_current_user()
        if current_user and users.is_current_user_admin():
            userquery = User.all()
            template_values = {
            'users':userquery
            }
            path = os.path.join(os.path.dirname(__file__), 'manageusers.html')
            self.response.out.write(template.render(path,template_values))
        else:
            self.redirect('/')
    def post(self):
        username = self.request.get('username')
        match = User.gql("WHERE username=:1 LIMIT 1",username)
        if match.get():
            template_values = {
            'user':match[0]
            }
        else:
            newuser = User(username=username,
                           fullname=username,
                           password='password',
                           monies=0.0)
            newuser.put()
            template_values = {
            'user':newuser
            }
        path = os.path.join(os.path.dirname(__file__),'edituser.html')
        self.response.out.write(template.render(path,template_values))

class EditUser(webapp.RequestHandler):
    """Edit a user"""
    def post(self):
        current_user = users.get_current_user()
        if current_user and users.is_current_user_admin():
            remove = self.request.get('remove')
            username = self.request.get('username')
            matching=User.gql("WHERE username=:1",username)
            firstmatch = matching[0]
            if remove:  
                firstmatch.delete()
                self.redirect('/manageusers')
            else:
                try:
                    fullname = self.request.get('fullname')
                    password = self.request.get('password')
                    setamount = float(self.request.get('setamount'))
                    addamount = abs(float(self.request.get('addamount')))
                    
                    firstmatch.fullname = fullname
                    firstmatch.password = password
                    firstmatch.monies = setamount
                    firstmatch.monies += addamount

                    firstmatch.put()
                    
                    self.redirect('/manageusers')
                except ValueError:
					template_values = {
					'message':'Please enter a floating point value in the amount fields.'
				    }
					path = os.path.join(os.path.dirname(__file__), 'submit_error.html')
					self.response.out.write(template.render(path,template_values))
        else:
            self.redirect('/')


def main():
    application = webapp.WSGIApplication([('/', MainPage),
                                        ('/pay', Pay),
                                        ('/history', History),
                                        ('/recent', Recent),
                                        ('/manageusers',ManageUsers),
                                        ('/edituser',EditUser)],
                                        debug=True)
    wsgiref.handlers.CGIHandler().run(application)

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
    buyer = db.UserProperty(required=True)
    date = db.DateTimeProperty(auto_now_add=True)
    items = db.StringListProperty()
    other = db.FloatProperty()
    total = db.FloatProperty()
    
class Item(db.Model):
    name = db.StringProperty(required=True)
    price = db.FloatProperty()

def UpdateUser(username,newname=None,newpw=None,newauthority=None):
    """Update a user in the database"""
    users = db.GqlQuery("SELECT * FROM User WHERE username = :1",username)
    for user in users:
        if newname:
            user.fullname=newname
        if newpw:
            user.password=newpw
        if newauthority:
            user.authority=newauthority
    db.put(users)

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

class Result(webapp.RequestHandler):
    """Returns Page with Results"""
    def __init__(self):
        self.coins = [1,5,10,25]
        self.coin_lookup = {25: "quarters", 10: "dimes", 5: "nickels", 1: "pennies"}

    def get(self):
        #Just grab the latest post
        collection = {}

        #select the latest input from the datastore
        change = db.GqlQuery("SELECT * FROM ChangeModel ORDER BY date DESC LIMIT 1")
        for c in change:
            change_input = c.input

        #coin change logic
        coin = self.coins.pop()
        num, rem  = divmod(change_input, coin)
        if num:
            collection[self.coin_lookup[coin]] = num
        while rem > 0:
            coin = self.coins.pop()
            num, rem = divmod(rem, coin)
            if num:
                collection[self.coin_lookup[coin]] = num

        template_values = {
        'collection': collection,
        'input': decimal.Decimal(change_input)/100,
        }

        #render template
        path = os.path.join(os.path.dirname(__file__), 'result.html')
        self.response.out.write(template.render(path, template_values))

class Change(webapp.RequestHandler):

    def post(self):
        """Printing Method For Recursive Results and While Results"""
        model = ChangeModel()
        try:
            change_input = decimal.Decimal(self.request.get('content'))
            model.input = int(change_input*100)
            model.put()
            self.redirect('/result')
        except decimal.InvalidOperation:
            path = os.path.join(os.path.dirname(__file__), 'submit_error.html')
            self.response.out.write(template.render(path,None))

class ManageUsers(webapp.RequestHandler):
	"""Find a user to edit"""
	def get(self):
		users = User.all()

		template_values = {
		'users':users
		}
		path = os.path.join(os.path.dirname(__file__), 'manageusers.html')
        self.response.out.write(template.render(path,template_values))
	def post(self):
		username = self.request.get('username')
		match = User.gql("WHERE username=:1 LIMIT 1",username)
		if match:
			template_values = {
			'


class EditItem(webapp.RequestHandler):
	def post(self):
		print 'lololol'

def main():
    application = webapp.WSGIApplication([('/', MainPage),
                                        ('/submit_form', Change),
                                        ('/result', Result),
                                        ('/recent', Recent)
										('/manageusers',ManageUsers)
										('/],
										#('/edititem',EditItem)],
                                        debug=True)
    wsgiref.handlers.CGIHandler().run(application)

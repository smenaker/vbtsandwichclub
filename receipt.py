from google.appengine.api.labs import taskqueue
from google.appengine.ext import webapp
from google.appengine.ext import db
from google.appengine.api import mail
from vbsandwich import User, Transaction, format_money, UTC, Pacific_tzinfo
import decimal
import wsgiref.handlers
import os
import datetime


class Receipt(webapp.RequestHandler):
    def post(self):
        user_key = self.request.get('user_key')
        transaction_key = self.request.get('transaction_key')
        user_match = User.get(user_key)
        transaction_match = Transaction.get(transaction_key)
        SendReceipt(user_match, transaction_match)

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


if __name__ == "__main__":
    application = webapp.WSGIApplication([('/receipt',Receipt),
                                         ])
    wsgiref.handlers.CGIHandler().run(application)

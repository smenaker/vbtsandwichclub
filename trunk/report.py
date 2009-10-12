#!/usr/bin/env python2.5

__author__ = 'Kevin Le'

import logging

from google.appengine.api import mail
from vbsandwich import User

if __name__ == "__main__":
    sender_address = 'voiceboxsandwichclub@gmail.com'
    user_address = 'tylers@voicebox.com'
    subject = 'Latest Sandwich Club Data'
    body = ''
    # Create a list of all the users, their names, and their balances.
    for user in User.all().order('username'):
        body += '%s\t%s\t%f\n'%(user.username,user.fullname,user.monies)
    mail.send_mail(sender_address,user_address,subject,body)

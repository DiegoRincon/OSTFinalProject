import time
import logging
import datetime
import os
import cgi
import urllib
import uuid
from google.appengine.api import users
from google.appengine.ext import ndb

import jinja2
import webapp2

JINJA_ENVT = jinja2.Environment(
      loader=jinja2.FileSystemLoader(os.path.dirname(__file__)), extensions=['jinja2.ext.autoescape'], autoescape=True)

DATETIME_FORMAT = "%d/%m/%Y %H:%M"

def resource_key(resId):
   """ Constructs a Datastore key for a Resource entity.
   """
   return ndb.Key('resId', resId)

class Author(ndb.Model):
   """Sub model for representing an author."""

   identity = ndb.StringProperty(indexed=False)
   email = ndb.StringProperty(indexed=True)

class MainPage(webapp2.RequestHandler):
   def get(self):

      resource_query = Resource.query(Resource.owner.email == users.get_current_user().email()).order(-Resource.timeCreated)
      resources = resource_query.fetch(1000)

      user = users.get_current_user()

      if user:
	 url = users.create_logout_url(self.request.uri)
	 url_linktext = 'logout'
      else:
	 url = users.create_login_url(self.request.uri)
	 url_linktext = 'Login'

      template_values = {
	    'user': user,
	    'resources': resources,
	    'url': url,
	    'url_linktext': url_linktext,
      }

      template = JINJA_ENVT.get_template('index.html')
      self.response.write(template.render(template_values))

class ResId(webapp2.RequestHandler):
   def get(self):
      resId = self.request.get('resId')
      time.sleep(2)
      resource_query = Resource.query(Resource.resourceId == resId)
      resource = resource_query.fetch(1)[0]
      logging.info(resource.name)

      template_values = {
	    'resource' : resource,
	    }

      template = JINJA_ENVT.get_template('resource.html')
      self.response.write(template.render(template_values))

class Resource(ndb.Model):
   owner = ndb.StructuredProperty(Author)
   name = ndb.StringProperty(indexed=False)
   startTime = ndb.DateTimeProperty(indexed=True)
   endTime = ndb.DateTimeProperty(indexed=True)
   tags = ndb.StringProperty(repeated=True)
   timeCreated = ndb.DateTimeProperty(auto_now_add=True)
   resourceId = ndb.StringProperty(indexed=True)


class Res(webapp2.RequestHandler):
   def post(self):
      name = self.request.get('name').strip()
      dateString = self.request.get('date').strip()
      startTimeString = self.request.get('start').strip()
      startTime = datetime.datetime.strptime(dateString + " " + startTimeString, DATETIME_FORMAT)
      endTimeString = self.request.get('end').strip()
      endTime = datetime.datetime.strptime(dateString + " " + endTimeString, DATETIME_FORMAT)
      tagString = self.request.get('tags').strip()
      tags = tagString.split(' ');
      resourceId = str(uuid.uuid1())

      author = Author(identity=users.get_current_user().user_id(), email=users.get_current_user().email())

       
      resource = Resource(parent=resource_key(resourceId),
	    owner=author,
	    name=name,
	    startTime=startTime,
	    endTime=endTime,
	    tags=tags,
	    resourceId = resourceId,
	    )
      resource.put()

      query_params = { 'resId' : resourceId }
      self.redirect('/resourceId?' + urllib.urlencode(query_params))

app = webapp2.WSGIApplication([
   ('/', MainPage),
   ('/resource', Res),
   ('/resourceId', ResId),
], debug=True)

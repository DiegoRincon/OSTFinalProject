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

def reservation_key(resId):
   return ndb.Key('resId', resId)

class Author(ndb.Model):
   """Sub model for representing an author."""

   identity = ndb.StringProperty(indexed=False)
   email = ndb.StringProperty(indexed=True)

class Reservation(ndb.Model):
   owner = ndb.StructuredProperty(Author)
   startTime = ndb.DateTimeProperty(indexed=True)
   duration = ndb.IntegerProperty(indexed=False)
   resource = ndb.StringProperty(indexed=True)
   reservationId = ndb.StringProperty(indexed=True)

class Resource(ndb.Model):
   owner = ndb.StructuredProperty(Author)
   name = ndb.StringProperty(indexed=False)
   startTime = ndb.DateTimeProperty(indexed=True)
   endTime = ndb.DateTimeProperty(indexed=True)
   tags = ndb.StringProperty(repeated=True)
   reservations = ndb.StructuredProperty(Reservation, repeated=True)
   timeCreated = ndb.DateTimeProperty(auto_now_add=True)
   resourceId = ndb.StringProperty(indexed=True)


class MainPage(webapp2.RequestHandler):
   def get(self):

      myEmail = users.get_current_user().email()
      resource_query = Resource.query(Resource.owner.email == myEmail).order(-Resource.timeCreated)
      resources = resource_query.fetch(1000)

      now = datetime.datetime.now()
      allResources_query = Resource.query(
	    ndb.query.AND(Resource.startTime >= now)).order(-Resource.startTime)
      allResources = allResources_query.fetch(1000)

      allResources[:] = [res for res in allResources if res.owner.email != myEmail]

      for resource in allResources:
	 if (resource.owner.email == myEmail):
	    allResources.remove(resource)


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
	    'allResources': allResources,
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

      template_values = {
	    'resource' : resource,
	    }

      template = JINJA_ENVT.get_template('resource.html')
      self.response.write(template.render(template_values))

class ReservationId(webapp2.RequestHandler):
   def get(self):
      resId = self.request.get('resId')
      time.sleep(2)
      reservation_query = Reservation.query(Reservation.reservationId == resId)
      reservation = reservation_query.fetch(1)[0]

      template_values = {
	    'reservation' : reservation,
	    }
      
      template = JINJA_ENVT.get_template('reservationId.html')
      self.response.write(template.render(template_values))

class MakeReservation(webapp2.RequestHandler):
   def get(self):
      resId = self.request.get('resId')
      time.sleep(2)
      resource_query = Resource.query(Resource.resourceId == resId)
      resource = resource_query.fetch(1)[0]
      template_values = {
	    'resource' : resource,
	    'date' : resource.startTime.date().strftime("%d/%m/%Y")
	    }
      template = JINJA_ENVT.get_template('makeReservation.html')
      self.response.write(template.render(template_values))

   def post(self):
      resId = self.request.get('resId')
      startTimeString = self.request.get('start').strip()
      duration = self.request.get('duration').strip()
      dateString = self.request.get('date').strip()

      author = Author(identity=users.get_current_user().user_id(), email=users.get_current_user().email())
      startTime = datetime.datetime.strptime(dateString + " " + startTimeString, DATETIME_FORMAT)
      resource_query = Resource.query(Resource.resourceId == resId)
      resource = resource_query.fetch(1)[0]

      reservationId = str(uuid.uuid1())
      
      reservation = Reservation(parent=reservation_key(reservationId),
	    owner=author,
	    startTime=startTime,
	    resource=resource.resourceId,
	    duration=int(duration),
	    reservationId=reservationId,
	    )
      reservation.put()
      resource.reservations.append(reservation)

      query_params = { 'resId' : reservationId }
      self.redirect('/reservationId?' + urllib.urlencode(query_params))

class MakeResource(webapp2.RequestHandler):
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
   ('/resource', MakeResource),
   ('/resourceId', ResId),
   ('/reservation', MakeReservation),
   ('/reservationId', ReservationId)
], debug=True)

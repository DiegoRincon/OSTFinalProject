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

class Interval(ndb.Model):
   startTime = ndb.TimeProperty(indexed=False)
   endTime = ndb.TimeProperty(indexed=False)

class Resource(ndb.Model):
   owner = ndb.StructuredProperty(Author)
   name = ndb.StringProperty(indexed=False)
   availabilityIntervals = ndb.StructuredProperty(Interval,repeated=True)
   startTime = ndb.DateTimeProperty(indexed=True)
   endTime = ndb.DateTimeProperty(indexed=True)
   tags = ndb.StringProperty(repeated=True)
   reservations = ndb.StringProperty(repeated=True)
   timeCreated = ndb.DateTimeProperty(auto_now_add=True)
   resourceId = ndb.StringProperty(indexed=True)

class Reservation(ndb.Model):
   owner = ndb.StructuredProperty(Author)
   startDate = ndb.DateTimeProperty(indexed=True)
   startTime = ndb.TimeProperty(indexed=True)
   duration = ndb.IntegerProperty(indexed=False)
   resource = ndb.StructuredProperty(Resource,indexed=True)
   reservationId = ndb.StringProperty(indexed=True)

class MainPage(webapp2.RequestHandler):
   def get(self):

      myEmail = users.get_current_user().email()
      resource_query = Resource.query(Resource.owner.email == myEmail).order(-Resource.timeCreated)
      resources = resource_query.fetch(1000)

      now = datetime.datetime.now()
      allResources_query = Resource.query(Resource.startTime >= now).order(-Resource.startTime)
      allResources = allResources_query.fetch(1000)
      allResources[:] = [res for res in allResources if res.owner.email != myEmail]

      reservations_query = Reservation.query(Reservation.startDate >= now).order(Reservation.startDate)
      reservations = reservations_query.fetch(1000)
      reservations[:] = [res for res in reservations if res.owner.email ==myEmail]

      user = users.get_current_user()
      nickname = str(user).split("@")[0]

      if user:
	 url = users.create_logout_url(self.request.uri)
	 url_linktext = 'logout'
      else:
	 url = users.create_login_url(self.request.uri)
	 url_linktext = 'Login'

      template_values = {
	    'user': nickname,
	    'resources': resources,
	    'reservations' : reservations,
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

      reservation_query = Reservation.query(Reservation.resource.resourceId == resId)
      reservations = reservation_query.fetch(100)

      template_values = {
	    'resource' : resource,
	    'reservations' : reservations,
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

def isTimeInInterval(timeStart, timeEnd, start, end):
   return (timeStart >= start and timeEnd <= end) or (timeStart < start and timeEnd > start) or (timeStart < end and timeEnd > end)

class MakeReservation(webapp2.RequestHandler):
   def get(self):
      resId = self.request.get('resId')
      error = self.request.get('error')
      time.sleep(2)
      resource_query = Resource.query(Resource.resourceId == resId)
      resource = resource_query.fetch(1)[0]
      
      reservation_query = Reservation.query(Reservation.resource.resourceId == resId)
      reservations = reservation_query.fetch(100)

      if (error != ""):
	 template_values = {
	    'resource' : resource,
	    'reservations' : reservations,
	    'date' : resource.startTime.date().strftime("%d/%m/%Y"),
	    'error' : "Reservation must be made within the availability period"
	 }
	 template = JINJA_ENVT.get_template('makeReservation.html')
	 self.response.write(template.render(template_values))
	 return
      
      template_values = {
	    'resource' : resource,
	    'reservations' : reservations,
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

      endTime = startTime + datetime.timedelta(minutes=int(duration))

      start = startTime.time()
      end = endTime.time()

      """
      Check that the reservation is within the start and end, and that it doesn't conflict
      with other reservations
      """
      
      if (isTimeInInterval(startTime, endTime, resource.startTime, resource.endTime) == False):
	 query_params = { 'error' : 1, 'resId' : resId }
	 self.redirect('/reservation?' + urllib.urlencode(query_params))
	 return


      if resource.availabilityIntervals:
	 for interval in resource.availabilityIntervals:
	    logging.info(str(interval))
	    if (isTimeInInterval(start,end,interval.startTime,interval.endTime)):
	       query_params = { 'error' : 1, 'resId' : resId }
	       self.redirect('/reservation?' + urllib.urlencode(query_params))
	       return

      reservationId = str(uuid.uuid1())
      
      reservation = Reservation(parent=reservation_key(reservationId),
	    owner=author,
	    startTime=startTime.time(),
	    startDate=startTime,
	    resource=resource,
	    duration=int(duration),
	    reservationId=reservationId,
	    )
      reservation.put()
      resource.reservations.append(reservation.reservationId)
      if resource.availabilityIntervals:
	 resource.availabilityIntervals.append(Interval(startTime=start, endTime=end))
      else:
	 resource.availabilityIntervals = [Interval(startTime=start,endTime=end)]

      resource.put()

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

      """
      availabilityIntervals = list(Interval(startTime.time(), endTime.time())
      """
       
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

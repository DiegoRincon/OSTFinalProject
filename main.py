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

"""TODO: Change this aweful hacky code: use pytz"""
def toUTC(date):
   return date + datetime.timedelta(hours=5)

def toEast(date):
   return date - datetime.timedelta(hours=5)

class Author(ndb.Model):
   """Sub model for representing an author."""
   nickname = ndb.StringProperty(indexed=False)
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
   timeCreated = ndb.DateTimeProperty(indexed=True)
   resourceId = ndb.StringProperty(indexed=True)
   lastReservation = ndb.DateTimeProperty(indexed=True)

class Reservation(ndb.Model):
   owner = ndb.StructuredProperty(Author)
   startDate = ndb.DateTimeProperty(indexed=True)
   endDate = ndb.DateTimeProperty(indexed=True)
   startTime = ndb.TimeProperty(indexed=True)
   duration = ndb.IntegerProperty(indexed=False)
   resource = ndb.StructuredProperty(Resource,indexed=True)
   reservationId = ndb.StringProperty(indexed=True)

class DeleteReservation(webapp2.RequestHandler):
   def get(self):
      reservationId = self.request.get('resId')
      reservation_query = Reservation.query(Reservation.reservationId == reservationId)
      reservation = reservation_query.fetch(1)[0]
      update = "Reservation for " + reservation.resource.name + " at " + reservation.startDate.strftime('%d/%b/%Y %H:%M') + " has been deleted."
      
      resource_query = Resource.query(Resource.resourceId == reservation.resource.resourceId)
      resource = resource_query.fetch(1)[0]

      resource.availabilityIntervals[:] = [inter for inter in resource.availabilityIntervals if not inter.startTime == reservation.startTime]
     
      resource.reservations[:] = [res for res in resource.reservations if not res == reservation.reservationId]
      resource.put()

      reservation.key.delete()
      query_params = { 'update' : update }
      time.sleep(1)
      self.redirect('/?' + urllib.urlencode(query_params))


class MainPage(webapp2.RequestHandler):
   def get(self):
      
      userId = self.request.get('user')
      update = self.request.get('update')
      displayAll = "true"
      if userId and userId == users.get_current_user().email():
	 self.redirect('/')
	 return
      elif userId:
	 displayAll = ""
      now = toEast(datetime.datetime.now())

      myEmail = users.get_current_user().email()
      resource_query = Resource.query(Resource.owner.email == myEmail).order(-Resource.timeCreated)
      resources = resource_query.fetch(1000)

      allResources_query = Resource.query(Resource.endTime >= now).order(Resource.endTime)
      allResources = allResources_query.fetch(1000)
      allResources[:] = [res for res in allResources if res.owner.email != myEmail]
      allResources.sort(key=lambda r: r.lastReservation)
      allResources.reverse()


      reservations_query = Reservation.query(Reservation.endDate >= now).order(Reservation.endDate, Reservation.startDate)
      reservations = reservations_query.fetch(1000)
      reservations[:] = [res for res in reservations if res.owner.email ==myEmail]
   
      if userId:
	 user = userId
      else:
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
	    'displayAll' : displayAll,
	    'update' : update,
      }

      template = JINJA_ENVT.get_template('index.html')
      self.response.write(template.render(template_values))

class ResourceId(webapp2.RequestHandler):
   def get(self):
      resId = self.request.get('resId')
      update = self.request.get('update')
      error = self.request.get('error')
      time.sleep(2)
      resource_query = Resource.query(Resource.resourceId == resId)
      resource = resource_query.fetch(1)[0]

      reservation_query = Reservation.query(Reservation.resource.resourceId == resId)
      reservations = reservation_query.fetch(100)


      template_values = {
	    'resource' : resource,
	    'reservations' : reservations,
	    'update' : update,
	    'error' : error,
	    'user' : users.get_current_user().email() 
	    }
      if users.get_current_user().email() != resource.owner.email:
	 query_params = { 'resId' : resId}
	 self.redirect('/reservation?' + urllib.urlencode(query_params))
	 return

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
      resourceId = self.request.get('resourceId')
      resId = self.request.get('resId')

      time.sleep(2)
      resource_query = Resource.query(Resource.resourceId == resId)
      resource = resource_query.fetch(1)[0]
      
      reservation_query = Reservation.query(Reservation.resource.resourceId == resId)
      reservations = reservation_query.fetch(100)

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
      dateString = self.request.get('date')
      logging.debug(dateString)
      
      resource_query = Resource.query(Resource.resourceId == resId)
      resource = resource_query.fetch(1)[0]
      
      reservation_query = Reservation.query(Reservation.resource.resourceId == resId)
      reservations = reservation_query.fetch(100)

      author = Author(
	    identity=users.get_current_user().user_id(),
	    email=users.get_current_user().email(),
	    nickname=users.get_current_user().email().split("@")[0]
	    )
	    
      try:
	 startTime = datetime.datetime.strptime(dateString + " " + startTimeString, DATETIME_FORMAT)
      except ValueError:
	 template_values = {
	    'resource' : resource,
	    'reservations' : reservations,
	    'error' : "Start time did not match format (hour:minute)"
	    }
         template = JINJA_ENVT.get_template('makeReservation.html')
         self.response.write(template.render(template_values))
	 return

      
      endTime = startTime + datetime.timedelta(minutes=int(duration))

      if (endTime > resource.endTime):
	 template_values = {
            'resource' : resource,
	    'reservations' : reservations,
	    'error' : "Reservation cannot go past End Time of Resource"
	 }
	 template = JINJA_ENVT.get_template('makeReservation.html')
	 self.response.write(template.render(template_values))
	 return
      if (startTime < resource.startTime):
	 template_values = {
	    'resource' : resource,
	    'reservations' : reservations,
	    'error' : "Reservation cannot start before Start Time of Resource"
	 }
	 template = JINJA_ENVT.get_template('makeReservation.html')
	 self.response.write(template.render(template_values))
	 return

      start = startTime.time()
      end = endTime.time()

      if (isTimeInInterval(startTime, endTime, resource.startTime, resource.endTime) == False):
	 template_values = {
	    'resource' : resource,
	    'reservations' : reservations,
	    'error' : "Reservation must be made within the resource availability period"
	 }
	 template = JINJA_ENVT.get_template('makeReservation.html')
	 self.response.write(template.render(template_values))
	 return

      if resource.availabilityIntervals:
	 for interval in resource.availabilityIntervals:
	    if (isTimeInInterval(start, end, interval.startTime, interval.endTime) == True):
	       template_values = {
		  'resource' : resource,
		  'reservations' : reservations,
		  'error' : "Reservation must be made within the availability period"
	       }
	       template = JINJA_ENVT.get_template('makeReservation.html')
	       self.response.write(template.render(template_values))
	       return

      reservationId = str(uuid.uuid1())
      
      reservation = Reservation(parent=reservation_key(reservationId),
	    owner=author,
	    startTime=startTime.time(),
	    startDate=startTime,
	    endDate=startTime + datetime.timedelta(minutes=int(duration)),
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
      resource.lastReservation = toEast(datetime.datetime.now())
      resource.put()
     
      
      query_params = { 'resId' : reservationId, 'resourceId' : resource.resourceId }
      self.redirect('/reservationId?' + urllib.urlencode(query_params))

class MakeResource(webapp2.RequestHandler):
   def get(self):
      template_values = { 'user' : users.get_current_user().email() }
      template = JINJA_ENVT.get_template('createResource.html')
      self.response.write(template.render(template_values))


   def post(self):
      name = self.request.get('name').strip()
      dateString = self.request.get('date').strip()
      startTimeString = self.request.get('start').strip()
      existingResId = self.request.get('resId')
      if not name:
	 template_values = {
	       'user' : users.get_current_user().email(),
	       'error' : "Name cannot be empty"
	       }
	 if existingResId:
	    query_params = { 'resId' : existingResId, 'error' : "Name cannot be empty" }
	    self.redirect('/resourceId?' + urllib.urlencode(query_params))
	 else:
	    template = JINJA_ENVT.get_template('createResource.html')
	    self.response.write(template.render(template_values))
	 return

      try:
	 startTime = datetime.datetime.strptime(dateString + " " + startTimeString, DATETIME_FORMAT)
      except ValueError:
	 template_values = {
	       'user' : users.get_current_user().email(),
	       'error' : "Date did not match format (dd/mm/yyy)"
	       }
	 if existingResId:
	    query_params = { 'resId' : existingResId, 'error' : "Date did not match format (dd/mm/yyy)" }
	    self.redirect('/resourceId?' + urllib.urlencode(query_params))
	 else:
	    template = JINJA_ENVT.get_template('createResource.html')
	    self.response.write(template.render(template_values))
	 return

      endTimeString = self.request.get('end').strip()
      try:
	 endTime = datetime.datetime.strptime(dateString + " " + endTimeString, DATETIME_FORMAT)
      except ValueError:
	 template_values = {
	       'user' : users.get_current_user().email(),
	       'error' : "Date did not match format (dd/mm/yyy)"
	       }
	 if existingResId:
	    query_params = { 'resId' : existingResId, 'error' : "Date did not match format (dd/mm/yyy)" }
	    self.redirect('/resourceId?' + urllib.urlencode(query_params))
	 else:
	    template = JINJA_ENVT.get_template('createResource.html')
	    self.response.write(template.render(template_values))
	 return

      if (endTime <= startTime):
	 template_values = {
	       'user' : users.get_current_user().email(),
	       'error' : "End Time must be later than start time"
	       }
	 if existingResId:
	    query_params = { 'resId' : existingResId, 'error' : "End Time must be later than start time" }
	    self.redirect('/resourceId?' + urllib.urlencode(query_params))
	 else:
	    template = JINJA_ENVT.get_template('createResource.html')
	    self.response.write(template.render(template_values))
	 return

      if (startTime <= toEast(datetime.datetime.now())):
	 template_values = {
	       'user' : users.get_current_user().email(),
	       'error' : "Start time cannot be in the past"
	       }
	 if existingResId:
	    query_params = { 'resId' : existingResId, 'error' : "Start time cannot be in the past" }
	    self.redirect('/resourceId?' + urllib.urlencode(query_params))
	 else:
	    template = JINJA_ENVT.get_template('createResource.html')
	    self.response.write(template.render(template_values))
	 return

      tagString = self.request.get('tags').strip()
      tags = tagString.split(' ');
      resourceId = str(uuid.uuid1())

      if existingResId:
	 resource_query = Resource.query(Resource.resourceId == existingResId)
	 res = resource_query.fetch(1)[0]
	 res.name = name
	 res.startTime = startTime
	 res.endTime = endTime
	 res.tags = tags
	 res.put()
	 query_params = { 'resId' : existingResId, 'update' : "You have successfully updated your resource!" }
	 self.redirect('/resourceId?' + urllib.urlencode(query_params))
	 return


      author = Author(
	    identity=users.get_current_user().user_id(),
	    email=users.get_current_user().email(),
	    nickname=users.get_current_user().email().split("@")[0]
	    )

      resource = Resource(parent=resource_key(resourceId),
	    owner=author,
	    name=name,
	    startTime=startTime,
	    endTime=endTime,
	    tags=tags,
	    resourceId = resourceId,
	    timeCreated = toEast(datetime.datetime.now()),
	    lastReservation = datetime.datetime.fromtimestamp(1),
	    )
      resource.put()

      query_params = { 'resId' : resourceId }
      self.redirect('/resourceId?' + urllib.urlencode(query_params))

class Tag(webapp2.RequestHandler):
   def get(self):
      tag = self.request.get('tag')
      resource_query = Resource.query(Resource.tags == tag).order(Resource.tags, Resource.startTime)

      resources = resource_query.fetch(1000)

      template_values = {
	    'resources' : resources,
	    'tag' : tag,
	    'user' : users.get_current_user().email()
	    }

      template = JINJA_ENVT.get_template('resources.html')
      self.response.write(template.render(template_values))

class RSSDump(webapp2.RequestHandler):
   def get(self):
      resId = self.request.get('resId')
      reservation_query = Reservation.query(Reservation.resource.resourceId == resId)
      reservations = reservation_query.fetch(100)
      resource_query = Resource.query(Resource.resourceId == resId)
      resource = resource_query.fetch(1)[0]
     
      template_values = {
	    'resource' : resource,
	    'reservations' : reservations,
	    }
      template = JINJA_ENVT.get_template('rssFeed.xml')
      self.response.headers['Content-Type'] = "application/xml"
      self.response.write(template.render(template_values))


app = webapp2.WSGIApplication([
   ('/', MainPage),
   ('/userId', MainPage),
   ('/resource', MakeResource),
   ('/resourceId', ResourceId),
   ('/reservation', MakeReservation),
   ('/reservationId', ReservationId),
   ('/tag', Tag),
   ('/createResource', MakeResource),
   ('/delRes', DeleteReservation),
   ('/rss', RSSDump), 
], debug=True)

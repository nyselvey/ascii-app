import os
import webapp2
import jinja2
import urllib2
import logging

from xml.dom import minidom
from google.appengine.api import memcache
from google.appengine.ext import db

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
                               autoescape = True)
#autoescape = True automatically escapes html


######### Templating #########
class MainHandler(webapp2.RequestHandler):
    def write(self, *a, **kw):
        self.response.out.write(*a, **kw)

    def render_str(self, template, **params):
    	t = jinja_env.get_template(template)
        return t.render(params)
        
    def render(self, template, **kw):
        self.write(self.render_str(template, **kw))

########### Making a Map ############
GMAPS_URL = "http://maps.googleapis.com/maps/api/staticmap?size=380x263&sensor=false&"
def gmaps_img(points):
	#returns a map with list of points passed in
	markers = '&'.join('markers=%s,%s' % (a.lat, a.lon)
						for a in points)
	return GMAPS_URL + markers

IP_URL = "http://api.hostip.info/?ip="

def get_coords(ip):
	url = IP_URL + ip
	content = None
	try:
		content = urllib2.urlopen(url).read()
	except URLError as e:
		logging.exception(e)
		return 

	if content:
		#if there is content
		#parse the xml and find the coordinates
		d = minidom.parseString(content)
		coords = d.getElementsByTagName("gml:coordinates")
		if coords and coords[0].childNodes[0].nodeValue:
			lon, lat = coords[0].childNodes[0].nodeValue.split(',')
			return db.GeoPt(lat, lon)

######### Art Database ##########
class Art(db.Model):
	# Art represents a an item of ascii art
	title = db.StringProperty(required = True)
	art = db.TextProperty(required = True)
	created = db.DateTimeProperty(auto_now_add = True)
	coords = db.GeoPtProperty()

######### Caching and Query ###########
def top_arts(update = False):
	key = 'top'
	arts = memcache.get(key)
	if arts is None or update:
		arts = db.GqlQuery("SELECT * from Art ORDER BY created DESC")
	arts = list(arts)
	memcache.set(key, arts)
	return arts

########### The website ###########
class MainPage(MainHandler):
	def render_front(self, title="", art="", error=""):
		arts = top_arts()
		points = filter(None, (a.coords for a in arts))
		img_url = None
		if points:
			img_url = gmaps_img(points)

		self.render("front.html", title=title, art=art, error=error, arts=arts, img_url=img_url)

	def get(self):
		return self.render_front()

	def post(self):
		title = self.request.get("title")
		art = self.request.get("art")

		#error handling
		if title and art:
			a = Art(title = title, art = art)
			coords = get_coords(self.request.remote_addr)
			if coords:
				a.coords = coords
			a.put()
			top_arts(True)

			self.redirect("/")
		else:
			error = "we need both a title and some artwork!"
			self.render_front(title, art, error)

app = webapp2.WSGIApplication([
    ('/', MainPage)
], debug=True)
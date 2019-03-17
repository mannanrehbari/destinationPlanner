from flask import Flask, render_template, request, redirect, jsonify
from flask import url_for, flash, Response, make_response

from flask import session
import random, string

import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm.exc import MultipleResultsFound

from models import Base, Country, DestSpot, User
import sys

# 3rd party library for authorization
from flask_oauthlib.client import OAuth


geocoder_key = "AIzaSyDIJaj7bbDWpnlzaATnmuupdqyR_l5WhVw"
import geocoder

app= Flask(__name__)
app.secret_key = "UV9lQOnAJFVwy6td5r6tOcFF"
with open('client_secret.json') as json_file:
    data= json.load(json_file)
    app.config['GOOGLE_ID'] = data['GOOGLE_ID']
    app.config['GOOGLE_SECRET'] = data['GOOGLE_SECRET']

# create an oauth object for this application
oauth = OAuth(app)
# configuration for authentication request
google = oauth.remote_app(
    'google',
    consumer_key=app.config.get('GOOGLE_ID'),
    consumer_secret=app.config.get('GOOGLE_SECRET'),
    request_token_params={
        'scope': 'email'
    },
    base_url='https://www.googleapis.com/oauth2/v1/',
    request_token_url=None,
    access_token_method='POST',
    access_token_url='https://accounts.google.com/o/oauth2/token',
    authorize_url='https://accounts.google.com/o/oauth2/auth',
)

engine=create_engine('sqlite:///countrydestinations.db?check_same_thread=False')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
dbsession = DBSession()

# for google maps marker
# gmaps_key = googlemaps.Client(key = "AIzaSyDIJaj7bbDWpnlzaATnmuupdqyR_l5WhVw")

def createUser(userdata):
    '''
    Creates a new user and returns id from userdata dict
    '''
    newUser = User(email=userdata["email"], picture=userdata["picture"])
    dbsession.add(newUser)
    dbsession.commit()
    user=dbsession.query(User).filter_by(email=userdata["email"]).one()
    return user.id

def getUserInfo(user_id):
    '''
    returns a user from an id
    '''
    user=dbsession.query(User).filter_by(id=user_id).one()
    return user

def getUserId(email):
    '''
    returns a userid if the user email exists
    '''
    try:
        user=dbsession.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None


@app.route('/')
@app.route('/index')
def index():
    '''
    If logged in: sends user data to home page
    userdata object will be a python dictionary
    If not logged in: render public page
    '''
    if 'google_token' in session:
        me = google.get('userinfo') # returns a oauthlib object
        userdata = me.data # we just need the data from me object
        return render_template('home.html', userdata=userdata)
    else:
        return render_template('pubhome.html')

@app.route('/login')
def login():
    '''
    if not already logged in, take user to login page
    '''
    if 'google_token' in session:
        return redirect(url_for('index'))
    else:
        return render_template('login.html')

@app.route('/logout')
def logout():
    '''
    Remove the google_token from session object
    '''
    if 'google_token' not in session:
        return redirect(url_for('index'))
    session.pop('google_token', None)
    message='Successfully logged out'
    flash(message)
    return redirect(url_for('index'))

@app.route('/callauthorize')
def callauthorize():
    '''
    This function initiates the google authentication if not logged in
    '''
    if 'google_token' in session:
        return redirect(url_for('index'))
    return google.authorize(callback=url_for('authorized', _external=True))

@app.route('/showlogin')
def showlogin():
    '''
    Show login page if not already logged in
    '''
    if 'google_token' in session:
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/authorized')
def authorized():
    '''
    Carries out the authentication process and returns a token
    '''
    if 'google_token' in session:
        return redirect(url_for('index'))

    resp = google.authorized_response()
    if resp is None:
        return 'Access denied: reason=%s error=%s' % (
            request.args['error_reason'],
            request.args['error_description']
        )
    session['google_token'] = (resp['access_token'], '')
    me = google.get('userinfo')
    userdata = me.data

    users = dbsession.query(User).all()
    check_user_id = getUserId(userdata["email"])
    if not check_user_id:
        check_user_id=createUser(userdata)
    userdata["user_id"]=check_user_id

    print(userdata, file=sys.stderr)
    return redirect(url_for('index'))

@google.tokengetter
def get_google_oauth_token():
    return session.get('google_token')

@app.route('/addcountry', methods=['GET', 'POST'])
def addcountry():
    '''
    Handles new country after logging in
    '''
    if 'google_token' not in session:
        message = 'Login to access the resource'
        flash(message)
        return redirect(url_for('index'))
    user_info_oauth = google.get('userinfo') # returns a oauthlib object
    userdata = user_info_oauth.data # we just need the data from me object
    curr_user_id = getUserId(userdata["email"])
    if request.method =='POST':
        newcountry = Country(name=request.form['countrySelect'], user_id=curr_user_id)
        checkcountry = dbsession.query(Country).filter_by(user_id=curr_user_id).all()

        exists = False
        for item in checkcountry:
            if newcountry.name == item.name:
                exists = True
        if not exists:
            dbsession.add(newcountry)
            dbsession.commit()
            message=''
            message += newcountry.name
            message += ' added to your country list!'
            flash(message)
        else:
            message='This country is already in your list!'
            flash(message)
        return redirect(url_for('addcountry'))
    else:
        allcountrycoors = []
        allcountrynames=[]
        listcountries = dbsession.query(Country).filter_by(user_id=curr_user_id).all()
        listlen = len(listcountries)
        for i in range(listlen):
            g = geocoder.google(listcountries[i].name, key=geocoder_key)
            countrycoors = g.latlng
            countryname = listcountries[i].name
            allcountrycoors.append(countrycoors)
            allcountrynames.append(countryname)
        # print(allcountrynames, file=sys.stderr)
        return render_template('addcountry.html', coors=allcountrycoors, allcountries=allcountrynames, countries=listcountries)

@app.route('/viewcountries' , methods=['GET', 'POST'])
def viewcountries():
    '''
    See the list of selected countries
    '''
    if 'google_token' not in session:
        message = 'Login to access the resource'
        flash(message)
        return redirect(url_for('index'))

    user_info_oauth = google.get('userinfo') # returns a oauthlib object
    userdata = user_info_oauth.data # we just need the data from me object
    curr_user_id = getUserId(userdata["email"])
    countries = dbsession.query(Country).filter_by(user_id=curr_user_id).order_by(Country.name).all()
    return render_template('viewcountries.html', countries=countries)

@app.route('/viewcountry/<int:countryid>', methods=['GET', 'POST'])
def viewcountry(countryid):
    '''
    renders each country page
    '''
    if 'google_token' not in session:
        message = 'Login to access the resource'
        flash(message)
        return redirect(url_for('index'))
    try:
        user_info_oauth = google.get('userinfo') # returns a oauthlib object
        userdata = user_info_oauth.data # we just need the data from me object
        curr_user_id = getUserId(userdata["email"])
        try:
            country=dbsession.query(Country).filter(Country.id==countryid, Country.user_id==curr_user_id).one()
        except:
            message = 'You are not allowed to access that resource'
            flash(message)
            return redirect(url_for('index'))
        gresponse = geocoder.google(country.name, key=geocoder_key)
        countrycoors = gresponse.latlng
        destinations = dbsession.query(DestSpot).filter(DestSpot.user_id==curr_user_id, DestSpot.country_id==countryid).all()
        print(destinations, file=sys.stderr)
        return render_template('viewcountry.html', country = country, coors = countrycoors, destinations=destinations)
    except NoResultFound:
        message='country with id: '
        message+=str(countryid)
        message += ' not in record!'
        flash(message)
        return render_template('home.html')

@app.route('/deletecountry/<int:countryid>', methods=['GET', 'POST'])
def deletecountry(countryid):
    '''
    This method deletes the country with given id
    '''
    if 'google_token' not in session:
        message = 'Login to access the resource'
        flash(message)
        return redirect(url_for('index'))
    try:
        countrydelete = dbsession.query(Country).filter_by(id=countryid).one()
    except NoResultFound:
        message='country with id: '
        message+=str(countryid)
        message += ' not in record!'
        flash(message)
        return redirect(url_for('viewcountries'))
    if request.method =='POST':
        ctdname = countrydelete.name
        dbsession.delete(countrydelete)
        dbsession.commit()
        message='The following country was deleted: '
        message+=ctdname
        flash(message)
        return redirect(url_for('viewcountries'))
    else:
        return render_template('deletecountry.html', country=countrydelete)

@app.route('/deletedestination/<int:countryid>/<int:destid>', methods=['GET', 'POST'])
def deletedestination(countryid, destid):
    '''
    This method deletes the destination with given id
    '''
    if 'google_token' not in session:
        message = 'Login to access the resource'
        flash(message)
        return redirect(url_for('index'))
    try:
        destdelete = dbsession.query(DestSpot).filter_by(id=destid).one()
        countrydd = dbsession.query(Country).filter_by(id=countryid).one()
    except NoResultFound:
        message='Destination with id: '
        message+=str(destid)
        message+=' for country with id: '
        message+=str(countryid)
        message += ' not in record!'
        flash(message)
        return redirect(url_for('viewdestination', countryid=countryid, destid=destid))
    if request.method =='POST':
        dtdname = destdelete.name
        dbsession.delete(destdelete)
        dbsession.commit()
        message='The following destination was deleted: '
        message+=dtdname
        flash(message)
        return redirect(url_for('viewcountry',countryid=countryid))
    else:

        return render_template('deletedestination.html', country=countrydd,dest=destdelete)

@app.route('/adddestination/<int:countryid>', methods=['GET', 'POST'])
def adddestination(countryid):
    '''
    renders the page for adding a new location within a country
    '''
    if 'google_token' not in session:
        message = 'Login to access the resource'
        flash(message)
        return redirect(url_for('index'))
    country=dbsession.query(Country).filter_by(id=countryid).one()
    return render_template('adddestination.html', country=country)

@app.route('/destinationadded', methods=['POST'])
def destinationadded():
    '''
    handles the ajax post request from adddestination.html
    '''
    if 'google_token' not in session:
        message = 'Login to access the resource'
        flash(message)
        return redirect(url_for('index'))
    lat = request.form['lat']
    lng = request.form['lng']
    countryid=request.form['countryid']
    address = request.form['address']

    # check if destination is already in db
    user_info_oauth = google.get('userinfo') # returns a oauthlib object
    userdata = user_info_oauth.data # we just need the data from me object
    curr_user_id = getUserId(userdata["email"])
    respstr = ''
    try:
        checkDest = dbsession.query(DestSpot).filter(DestSpot.name==address,DestSpot.user_id==curr_user_id).one()
        respstr += address
        respstr += '-- already exists in your list'
    except NoResultFound:
        defdes = ''
        newdest = DestSpot(name=address, destlat=lat, destlng=lng, user_id=curr_user_id, country_id=countryid, destdescription=defdes)
        dbsession.add(newdest)
        dbsession.commit()
        respstr += 'Success! '
        respstr += address
        respstr += ' was added to your list'

    resp =make_response(json.dumps(respstr))
    return resp

@app.route('/viewdestination/<int:countryid>/<int:destid>', methods=['GET'])
def viewdestination(countryid, destid):
    '''
    view each destination within a given country
    '''
    if 'google_token' not in session:
        message = 'Login to access the resource'
        flash(message)
        return redirect(url_for('index'))
    country=dbsession.query(Country).filter_by(id=countryid).one()
    dest = dbsession.query(DestSpot).filter_by(id=destid).one()
    return render_template('viewdestination.html', country=country, dest=dest)

@app.route('/adddescription/<int:countryid>/<int:destid>', methods=['GET', 'POST'])
def adddescription(countryid, destid):
    '''
    handles description for destination
    '''
    if 'google_token' not in session:
        message = 'Login to access the resource'
        flash(message)
        return redirect(url_for('index'))
    if request.method=='POST':
        newdescription = request.form['newDesc']
        updateDest = dbsession.query(DestSpot).filter_by(id=destid).one()
        updateDest.destdescription = newdescription
        dbsession.add(updateDest)
        dbsession.commit()
        updatemessage = 'Description added!'
        flash(updatemessage)
        return redirect(url_for('viewdestination', countryid=countryid, destid=destid))
    else:
        destination= dbsession.query(DestSpot).filter_by(id=destid).one()
        return render_template('adddescription.html', countryid=countryid, dest=destination)

@app.route('/modifydescription/<int:countryid>/<int:destid>', methods=['GET', 'POST'])
def modifydescription(countryid, destid):
    '''
    modification requires the text of description so has to be separate from adding desc
    '''
    if 'google_token' not in session:
        message = 'Login to access the resource'
        flash(message)
        return redirect(url_for('index'))
    if request.method=='POST':
        newdescription = request.form['newDesc']
        updateDest = dbsession.query(DestSpot).filter_by(id=destid).one()
        updateDest.destdescription = newdescription
        dbsession.add(updateDest)
        dbsession.commit()
        updatemessage = 'Description updated!'
        flash(updatemessage)
        return redirect(url_for('viewdestination', countryid=countryid, destid=destid))
    else:
        dest= dbsession.query(DestSpot).filter_by(id=destid).one()
        return render_template('modifydescription.html', countryid=countryid, dest=dest)

if __name__ == '__main__':
    app.debug=True
    app.run(host='0.0.0.0', port=5000)

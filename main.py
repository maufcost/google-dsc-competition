# Import required modules for application logic
import time
import string
import random
import json
import base64
import random
# Import required modules for Flask execution
from flask import Flask, render_template, request, redirect

# Google Cloud product modules
from google.auth.transport import requests
from google.cloud import datastore
import google.oauth2.id_token
from google.cloud import storage

# Initialize objects to handle Authentication, database storage, and FLask
firebase_request_adapter = requests.Request()
datastore_client = datastore.Client()
app = Flask(__name__)

####################{UTILITY FUNCTIONS BEGIN HERE}########################


# Generates a random string with specified length using lower and uppercase alphabet + digits
# default len is 6
def random_string_digits(string_len=6):
    lettersAndDigits = string.ascii_letters + string.digits
    return ''.join(random.choice(lettersAndDigits) for i in range(string_len))

# Does some base64 magic to get the img
# blob and send this to our cloud bucket.

def blobify(img_data):
    img_blob = base64.b64decode(img_data)
    return img_blob

def upload_blob(file, destination_blob_name):

    storage_client = storage.Client() # Opens a storage client
    bucket = storage_client.bucket("stickerbucket") #our bucket name
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_string(file, content_type='image/png') #, content_type="image/png"

####################{UTILITY FUNCTIONS END HERE}#######################



# def store_time(dt):
#     entity = datastore.Entity(key=datastore_client.key('visit'))
#     entity.update({
#         'timestamp': dt
#     })
#
#     datastore_client.put(entity)
# def fetch_times(limit):
#     query = datastore_client.query(kind='visit')
#     query.order = ['-timestamp']
#
#     times = query.fetch(limit=limit)
#
#     return times

####################{DATABASE FUNCTIONS BEGIN HERE}#########################


# Creates a new user in the database with the information given
# Returns a randomly generated userid that is associated with the user
def create_user(email, name, type, cid, pic_id):
    complete_key = datastore_client.key('User', email)

    task = datastore.Entity(key=complete_key)
    random_uid = random_string_digits() + "u" + random_string_digits()

    task.update({
        'uid': random_uid,
        'name': name,
        'type': type,
        'cid': cid,
        'pic_id': pic_id
    })

    datastore_client.put(task)
    return random_uid

# Attemps to get an user by the email.
# If the email is not in the database, it returns False
# Otherwise, it returns the record of the user
def get_user(email):
    thekey = datastore_client.key('User', email) #Make a key with the email
    query = datastore_client.get(thekey)

    if query == None:
        return False
    return query

# Creates a post with ownership of UID & CID
# Returns generated postID
def create_post(uid, mid, description, cid):
    random_postid = random_string_digits() + "p" + random_string_digits()
    complete_key = datastore_client.key('Posts', random_postid)
    task = datastore.Entity(key=complete_key)

    task.update({
        'uid': uid, # owner
        'mid': mid, # empty if no media, else str that correspond to GCS
        'description': description,
        'cid': cid # company associated with
    })

    datastore_client.put(task)
    return random_postid

# Creates a comment owned by uid about postid with a content message
# Returns the generated commentId for future features like reply, etc.
def create_comment(postid, commid, uid, content):
    random_commid = random_string_digits() + "c" + random_string_digits()
    complete_key = datastore_client.key('Comments', random_commid)
    task = datastore.Entity(key=complete_key)

    task.update({
        'postid': postid,
        'uid': uid, # owner of the comment
        'content': content,
        'ts': time.time() #Current timestamp in seconds (this will be used to sort the comments :D)
    })

    datastore_client.put(task)
    return random_commid

# Get all comments from the post specified
def get_comments_from_post(postid):
    query = datastore_client.query(kind='Comments')
    query.add_filter('postid', '=', postid)
    query.order = ["ts"] #Order by timestamp from the most recent first
    results = list(query.fetch())
    return results


# Create a like entry in the database
def like_post(postid, uid):
    the_key = postid + uid
    complete_key = datastore_client.key('Likes', the_key)
    task = datastore.Entity(key=complete_key)

    task.update({
        'postid': postid,
        'uid': uid, # owner of the comment
    })

    datastore_client.put(task)

# Dislike the post by deleting the like entry
def dislike_post(postid, uid):
    the_key = postid + uid
    key = datastore_client.key('Likes',the_key)
    datastore_client.delete(key)

# Get the list of users that liked the post
# as well as the count of likes using len()
def get_users_that_liked(postid):
    query = datastore_client.query(kind='Likes')
    query.add_filter('postid', '=', postid)
    results = list(query.fetch())
    return results

# Creates a company/organization
# This is triggered only by new company representatives
# Returns a randomly generated company/organization id + random secret key
def create_org(cname, pic_id, uid):
    random_cid = random_string_digits() + "o" + random_string_digits()
    random_secret_key = random_string_digits(5) + "N-4" + random_string_digits(5) + "T-3" + random_string_digits(6)

    complete_key = datastore_client.key('Companies', random_cid)
    task = datastore.Entity(key=complete_key)

    task.update({
        'cname': cname,
        'pic_id': pic_id,
        'uid': uid, # Primary creator of the org
        'secret': random_secret_key
    })

    datastore_client.put(task)
    return {'cid':random_cid, 'secret':random_secret_key}

# Rewrite/Update the entry to add the user as a company representative
def add_person_to_cid(email, cid):
    key = datastore_client.key('User',email)
    task = datastore_client.get(key)

    task['cid'] = cid
    task['type'] = 2 #company rep

    datastore_client.put(task)

####################{DATABASE FUNCTIONS END HERE}#########################


####################{SERVER FUNCTIONS BEGIN HERE}#########################

@app.route('/')
def root():
    id_token = request.cookies.get("token") # Check for firebase token
    error_message = None
    claims = None
    currentAmountOfPoints = 0

    if id_token:
        try:
            # Verify the token against the Firebase Auth API.
            claims = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
            user_data = get_user(claims['email'])

            # If there's no valid user data, this person needs to register first
            if user_data != False:
                return redirect("/otherpage") #To change to main page perhaps
            else:
                return redirect("/register")

        except ValueError as exc:
            # This will be raised if the token is expired or any other
            # verification checks fail.
            error_message = str(exc)

    return render_template('login.html', user_data=claims, error_message=error_message)

@app.route('/register')
def register_page():
    id_token = request.cookies.get("token") # Check for firebase token
    error_message = None
    claims = None

    if id_token:
        try:
            # Verify the token against the Firebase Auth API.
            claims = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
            user_data = get_user(claims['email'])

            # If there's no valid user data, this person needs to register first
            if user_data != False:
                return redirect("/otherpage") #This user already exists, just go to homepage.

            else: # User will have a form to fill up the information there
                return render_template('register.html', user_data=claims, error_message=error_message)

        except ValueError as exc:
            error_message = str(exc)

    return render_template('login.html', user_data=claims, error_message=error_message)

@app.route('/newuser', methods=['POSt'])
def add_user_to_db():
    # create_user(email, name, type, cid, pic_id):
    email = request.form.get('email')
    name = request.form.get('name')
    type = request.form.get('type')
    cid = request.form.get('cid')

    # Get image if it exists.
    img = request.form.get('img')
    pid = ""
    if img != None:
        pid = random_string_digits(4) + "p" + random_string_digits(8)
        blobdata = blobify(img.split(',')[1])
        upload_blob(blobdata,pid)

    create_user(email, name, type, cid, pid)
    return redirect("/otherpage")


@app.route('/logout')
def logout():
    return render_template('login.html')

####################{SERVER FUNCTIONS END HERE}#########################

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)

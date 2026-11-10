import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import datetime
from google.cloud.firestore import FieldFilter

# Initialize Firebase App
cred = credentials.Certificate("sigma1tv-firebase-adminsdk-fbsvc-3e5fe65da4.json") # اسم ملف المفاتيح اللي هتنزله من فايربيز
firebase_admin.initialize_app(cred)

db = firestore.client()

def init_db():
    # Firestore doesn't require explicit table creation (schema-less), 
    # collections are created automatically when data is added.
    print("Connected to Firebase Firestore successfully!")

def get_cached_folder_id(folder_name):
    """
    Checks if the folder exists in Firestore cache collection.
    """
    docs = db.collection('folders').where('folder_name', '==', folder_name).stream()
    for doc in docs:
        data = doc.to_dict()
        return data.get('gofile_folder_id')
    return None

def cache_folder_id(folder_name, gofile_folder_id):
    """
    Saves the folder mapping in Firestore.
    """
    db.collection('folders').add({
        'folder_name': folder_name,
        'gofile_folder_id': gofile_folder_id,
        'created_at': datetime.datetime.utcnow()
    })

def save_upload(user_id, folder_name, file_name, download_link):
    """
    Saves upload history in Firestore.
    """
    db.collection('uploads').add({
        'user_id': user_id,
        'folder_name': folder_name,
        'file_name': file_name,
        'download_link': download_link,
        'upload_date': datetime.datetime.utcnow()
    })

def get_user_uploads(user_id):
    """
    Retrieves user upload history from Firestore using the modern 'filter' syntax.
    """
    docs = db.collection('uploads')\
               .where(filter=FieldFilter('user_id', '==', user_id))\
               .order_by('upload_date', direction=firestore.Query.DESCENDING)\
               .limit(10)\
               .stream()
               
    records = []
    for doc in docs:
        data = doc.to_dict()
        records.append((
            data.get('folder_name'),
            data.get('file_name'),
            data.get('download_link'),
            str(data.get('upload_date'))
        ))
    return records
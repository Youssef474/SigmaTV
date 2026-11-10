import requests
# استيراد إعدادات وحافظة الفايربيز بتاعت المشروع
from database import db  # نفترض أن db هو كائن اتصال الـ Firestore عندك

def get_gofile_server():
    try:
        response = requests.get("https://api.gofile.io/servers")
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "ok":
                return data.get("data", {}).get("servers", [{}])[0].get("name")
        return None
    except Exception as e:
        print(f"Error server: {e}")
        return None

def get_cached_folder_from_firestore(folder_name):
    """جلب الـ ID من فايربيز لو المسلسل متسجل قبل كده"""
    try:
        doc_ref = db.collection('gofile_folders').document(folder_name)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict().get('folder_id')
    except Exception as e:
        print(f"Firebase read error: {e}")
    return None

def cache_folder_to_firestore(folder_name, folder_id):
    """حفظ الـ ID الجديد للمسلسل في فايربيز"""
    try:
        db.collection('gofile_folders').document(folder_name).set({
            'folder_name': folder_name,
            'folder_id': folder_id
        })
    except Exception as e:
        print(f"Firebase write error: {e}")

def create_gofile_folder(folder_name, parent_folder_id, token):
    url = "https://api.gofile.io/contents/createFolder"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "parentFolderId": parent_folder_id,
        "folderName": folder_name,
        "public": "true"
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        res_json = response.json()
        print(f"Folder API Response ({folder_name}):", res_json)
        
        if response.status_code == 200 and res_json.get("status") == "ok":
            return res_json.get("data", {}).get("id")
    except Exception as e:
        print(f"Error folder creation exception: {e}")
        
    return None

def upload_to_gofile_nested(file_path, main_folder_name, sub_folder_name, file_display_name, token):
    server = get_gofile_server()
    if not server:
        print("Error: Could not get GoFile server.")
        return None
        
    # الخطوة 1: فحص Firebase هل فولدر المسلسل الأساسي موجود قبل كده؟
    main_folder_id = get_cached_folder_from_firestore(main_folder_name)
    
    if not main_folder_id:
        # لو مش موجود، بننشئه تحت الفولدر الرئيسي الثابت أو الجذر العام لحسابك
        BASE_PARENT_ID = "e1501792-651b-4a78-a060-e71734d9fe0b" # أو الجذر المتاح
        
        main_folder_id = create_gofile_folder(main_folder_name, BASE_PARENT_ID, token)
        if not main_folder_id:
            print("Failed to create main series folder in GoFile")
            return None
        
        # حفظه فوراً في Firebase عشان ما ننشئوش تاني أبداً
        cache_folder_to_firestore(main_folder_name, main_folder_id)

    # الخطوة 2: إنشاء فولدر الحلقة الفرعي تحت فولدر المسلسل الجاي من فايربيز
    sub_folder_id = create_gofile_folder(sub_folder_name, main_folder_id, token)
    if not sub_folder_id:
        print("Failed to create episode sub folder")
        return None

    # الخطوة 3: رفع الملف جوه فولدر الحلقة المعزول
    upload_url = f"https://{server}.gofile.io/contents/uploadfile"
    
    try:
        with open(file_path, "rb") as file_data:
            files = {"file": (file_display_name, file_data)}
            headers = {"Authorization": f"Bearer {token}"}
            data = {"folderId": sub_folder_id}
                
            response = requests.post(upload_url, data=data, files=files, headers=headers)
            res_json = response.json()
            print("Upload Response:", res_json)
            
        if response.status_code == 200 and res_json.get("status") == "ok":
            return res_json.get("data", {}).get("downloadPage")
        return None
    except Exception as e:
        print(f"Upload error exception: {e}")
        return None
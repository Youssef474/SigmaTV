import os
import telebot
from database import init_db, save_upload,get_user_uploads,db
import urllib.parse
from gofile_uploader import upload_to_gofile_nested
from telebot import types



TELEGRAM_BOT_TOKEN ="9052379107:AAEnjOff1Y8y0F8CjaBmLGg_yxCN3x7qqs0"

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

GOFILE_TOKEN = "KKZQ3y3CmjNB950FCwg5KXtxsfrKUsxV" # Leave empty "" if not needed

init_db()

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(
        message, 
        "Welcome to Organized Sigma Uploader! 🚀\n\n"
        "Send a video with a caption like:\n`the walking dead s1 /e1`\n"
        "It will automatically create a folder and organize your files!"
    )

@bot.message_handler(commands=['history'])
def show_history(message):
    user_id = message.from_user.id
    uploads = get_user_uploads(user_id)
    
    if not uploads:
        bot.reply_to(message, "📭 No uploads found.")
        return
        
    history_text = "📂 **Your Organized Uploads:**\n\n"
    for idx, (folder, file_name, link, date) in enumerate(uploads[:10], 1):
        history_text += f"{idx}. 📁 **{folder}** ➡️ `{file_name}`\n🔗 {link}\n\n"
        
    bot.reply_to(message, history_text, parse_mode="Markdown")

# ... (باقي الاستيرادات)

@bot.message_handler(content_types=['video', 'document','photo'])
def handle_docs_videos(message):


    caption = message.caption or ""
    
    # تأمين تقسيم الكابتشن عشان لو نسيت الفاصل البوت ما يقفش
    if "/" in caption:
        parts = caption.split("/")
        main_folder = parts[0].strip()
        sub_folder = parts[1].strip() if len(parts) > 1 else "حلقة خاصة"
        file_display_name = f"{sub_folder}.mp4"
    else:
        main_folder = "مفردات عامة"
        sub_folder = caption.strip() or "حلقة جديدة"
        file_display_name = f"{sub_folder}.mp4"

    sent_msg = bot.reply_to(message, f"Wait...")
    # تنزيل الملف مؤقتاً
    file_info = bot.get_file(message.video.file_id if message.video else message.documepnt.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    temp_path = "temp_video.mp4"
    with open(temp_path, 'wb') as new_file:
        new_file.write(downloaded_file)

    # الرفع بنظام الفولدر المتداخل (Nested Folders)
    gofile_link = upload_to_gofile_nested(temp_path, main_folder, sub_folder, file_display_name, GOFILE_TOKEN)

    if gofile_link:
        save_upload(message.from_user.id, f"{main_folder}/{sub_folder}", file_display_name, gofile_link)
        
        # تجهيز اسم الملف وتنسيقه ليكون مناسباً لمسار الـ URL على Worker
        safe_filename = file_display_name.replace(" ", "_").replace(".", "_")
            
        # رابط الصفحة الديناميكي بناءً على السكربت بتاع Cloudflare Worker
        final_page_url = f"https://sigmatv.vercel.app/ep_{safe_filename}.html?download={urllib.parse.quote(gofile_link)}"

        bot.edit_message_text(
            f"✅ تم الرفع بنظام الفولدرات المعزولة بنجاح!\n\n"
            f"📁 المسلسل: {main_folder}\n"
            f"🎬 فولدر الحلقة: {sub_folder}\n\n"
            f"🔗 رابط صفحة الهبوط الخاصة بالحلقة:\n{final_page_url}",
            chat_id=sent_msg.chat.id,
            message_id=sent_msg.message_id,
            disable_web_page_preview=True
        )
    else:
        bot.edit_message_text("❌ حدث خطأ أثناء الرفع!", chat_id=sent_msg.chat.id, message_id=sent_msg.message_id)


# النطاق الأساسي لموقعك على Vercel
WEBSITE_DOMAIN = "https://sigmatv.vercel.app"


def generate_episode_page(file_name, download_link):
    """
    تولد صفحة HTML خاصة بالحلقة وتحقن اسم الملف ورابط التحميل مباشرة داخل الكود.
    """
    template_path = "index.html"
    if not os.path.exists(template_path):
        return None

    with open(template_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    # إنشاء اسم ملف فريد وآمن للرابط
    safe_filename_slug = "".join([c if c.isalnum() else "_" for c in file_name])
    output_filename = f"ep_{safe_filename_slug}.html"
    
    output_dir = "generated_pages"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    output_path = os.path.join(output_dir, output_filename)

    # تعديل الجافاسكريبت مباشرة داخل الصفحة بالاسم الحقيقي والرابط
    # بنبحث عن المتغيرات ونحط جواها الداتا بتاعت الحلقة الجديدة فوراً
    html_content = html_content.replace(
        'const dynamicFileName = "%%FILE_NAME%%";',
        f'const dynamicFileName = "{file_name}";'
    )
    html_content = html_content.replace(
        'const dynamicDownloadLink = "%%DOWNLOAD_LINK%%";',
        f'const dynamicDownloadLink = "{download_link}";'
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    
    return output_filename


ADMIN_IDS = [7679712660]  # استبدل  ده بـ آيدي حسابك الحقيقي

@bot.message_handler(commands=['list'])
def list_folders_command(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "⛔ عذراً يا سيجما، هذا الأمر مخصص للأدمن فقط.")
        return

    try:
        docs = db.collection('uploads').stream()
        folders = set()
        for doc in docs:
            data = doc.to_dict()
            if isinstance(data, dict) and 'folder_name' in data:
                raw_folder = data['folder_name']
                # استخراج الماين فولدر الرئيسي فقط قبل أي علامة مائلة / أو \
                main_folder = raw_folder.split('/')[0].split('\\')[0].strip()
                folders.add(main_folder)
                
        if not folders:
            bot.reply_to(message, "⚠️ مفيش أي فولدرات رئيسية مسجلة في قاعدة البيانات حتى الآن يا سيجما.")
            return

        markup = types.InlineKeyboardMarkup(row_width=1)
        for folder in folders:
            markup.add(types.InlineKeyboardButton(f"📁 الفولدر الرئيسي: {folder}", callback_data=f"select_folder_{folder}"))
            
        bot.reply_to(message, "🎬 **اختر الفولدر الرئيسي لعرض حلقاته المرتبطة:**", reply_markup=markup, parse_mode="Markdown")
        
    except Exception as e:
        bot.reply_to(message, f"❌ حدث خطأ أثناء جلب البيانات: {str(e)}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('select_folder_'))
def folder_selected_callback(call):
    folder_name = call.data.replace('select_folder_', '')
    
    try:
        docs = db.collection('uploads').stream()
        episodes_list = []
        for doc in docs:
            data = doc.to_dict()
            # التأكد إن الـ data عبارة عن ديكشنري عشان مانخدش خطأ الـ str
            if isinstance(data, dict):
                f_name = data.get('folder_name', '')
            if folder_name in f_name:
                episodes_list.append(data)

        if not episodes_list:
            bot.answer_callback_query(call.id, "⚠️ هذا الفولدر فارغ ولا يحتوي على حلقات.")
            return

       # رأس الرسالة النظيف والمنسق بدون أي بيانات خام تسربت بالخطأ
        response_text = f"🔥 قائمة حلقات الفولدر الرئيسي: {folder_name}\n"
        response_text += "━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for index, ep in enumerate(episodes_list, start=1):
            file_name = ep.get('file_name', f'الحلقة {index}')
            download_link = ep.get('download_link', '#')
            
            # تنظيف رابط التحميل لو فيه قوس زيادة أو علامة مش مطلوب تؤثر على الرابط
            download_link = download_link.replace("{", "").replace("}", "").strip()
            
            encoded_name = urllib.parse.quote(file_name)
            encoded_download = urllib.parse.quote(download_link)
            final_page_url = f"{WEBSITE_DOMAIN}/?download={encoded_download}&name={encoded_name}"
            
            response_text += f"🎬 #{index:02d} | {file_name}\n"
            response_text += f"🔗 رابط المشاهدة والتحميل:\n{final_page_url}\n"
            response_text += "─────────────────────\n"

        response_text += "\n✨ *جميع الحلقات مرفوعة بأعلى جودة وسيرفرات مباشرة بدون إعلانات مزعجة.*"

        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📢 نعم، انشرها للجروب", callback_data=f"publish_yes_{folder_name}"),
            types.InlineKeyboardButton("❌ لا، إلغاء", callback_data="publish_no")
        )

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=response_text,
            reply_markup=markup,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ حدث خطأ: {str(e)}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('publish_'))
def publish_decision_callback(call):
    if call.data == "publish_no":
        bot.answer_callback_query(call.id, "تم الإلغاء يا سيجما.")
        bot.delete_message(call.message.chat.id, call.message.message_id)
        return
        
    if call.data.startswith('publish_yes_'):
        folder_name = call.data.replace('publish_yes_', '')
        TARGET_GROUP_ID = "@sigma1tv" # حط آيدي الجروب هنا
        
        try:
            docs = db.collection('uploads').stream()
            episodes_list = []
            for doc in docs:
                data = doc.to_dict()
                # التأكد إن الـ data عبارة عن ديكشنري عشان مانخدش خطأ الـ str
                if isinstance(data, dict):
                    f_name = data.get('folder_name', '')
                    if folder_name in f_name:
                        episodes_list.append(data)
            
            response_text = f"🔥 **إصدارات جديدة وحصرية على SIGMA TV**\n"
            response_text += f"📁 **مسلسل : {folder_name}**\n"
            response_text += "━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            for index, ep in enumerate(episodes_list, start=1):
                file_name = ep.get('file_name', f'الحلقة {index}')
                download_link = ep.get('download_link', '#')
                
                encoded_name = urllib.parse.quote(file_name)
                encoded_download = urllib.parse.quote(download_link)
                final_page_url = f"{WEBSITE_DOMAIN}/?download={encoded_download}&name={encoded_name}"
                
                response_text += f"🎬 **#{index:02d} | {file_name}**\n"
                response_text += f"🔗 [رابط التحميل المباشر]({final_page_url})\n"
                response_text += "─────────────────────\n"

            bot.send_message(TARGET_GROUP_ID, response_text, parse_mode="Markdown", disable_web_page_preview=True)
            bot.answer_callback_query(call.id, "✅ تم نشر القائمة في الجروب بنجاح!", show_alert=True)
            bot.delete_message(call.message.chat.id, call.message.message_id)
            
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ فشل النشر: {str(e)}", show_alert=True)


if __name__ == "__main__":
    print("Advanced Bot is running...")
    bot.infinity_polling()
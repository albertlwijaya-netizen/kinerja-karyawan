import pymysql
import certifi # Import library certifi

def get_db_connection():
    connection = pymysql.connect(
        host='gateway01.ap-southeast-1.prod.alicloud.tidbcloud.com',
        port=4000,
        user='8NtwncxmEMec1zz.root',
        password='PWBBZNhopb38KusE',
        database='KARYAWAN',
        cursorclass=pymysql.cursors.DictCursor,
        # Gunakan certifi.where() agar berfungsi di Windows maupun Linux
        ssl={'ca': certifi.where()} 
    )
    return connection

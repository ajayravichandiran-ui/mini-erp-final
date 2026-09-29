import PyInstaller.__main__

PyInstaller.__main__.run([
    'app.py',
    '--name=AJ_ERP',
    '--windowed',
    '--hidden-import=flask',
    '--hidden-import=groq',
    '--hidden-import=sklearn',
    '--add-data=templates;templates',
    '--add-data=erp_database.db;.',
    '--add-data=model.pkl;.'
])
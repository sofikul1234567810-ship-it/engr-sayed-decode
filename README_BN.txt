TELEGRAM HTML DECODER BOT — SETUP

1) Python 3.10+ install করুন।
2) এই folder-এ terminal/command prompt খুলুন।
3) Run:
   pip install -r requirements.txt

4) Telegram-এ @BotFather খুলে /newbot দিন, bot token নিন।
5) Token environment variable হিসেবে সেট করুন:

Linux / Termux:
   export BOT_TOKEN='YOUR_BOT_TOKEN'
   python bot.py

Windows CMD:
   set BOT_TOKEN=YOUR_BOT_TOKEN
   python bot.py

Windows PowerShell:
   $env:BOT_TOKEN='YOUR_BOT_TOKEN'
   python bot.py

তারপর Telegram-এ নিজের bot-এ /start দিন এবং .html/.js ফাইল পাঠান।

গুরুত্বপূর্ণ:
- Bot uploaded code execute করে না।
- এটি HTML entity decode, কিছু Base64 text block decode এবং JS formatting করে।
- Custom encryption, checksum-locked wrapper বা complex obfuscation-এর ক্ষেত্রে
  সম্পূর্ণ original source স্বয়ংক্রিয়ভাবে ফিরে পাওয়ার নিশ্চয়তা নেই।
- Token কারও সাথে শেয়ার করবেন না।

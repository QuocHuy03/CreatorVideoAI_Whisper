from gtts import gTTS

text_ur = "زندگی ایک خوبصورت سفر ہے۔ ہر دن ایک نیا موقع ہوتا ہے۔ ہمیں اپنے خوابوں کے پیچھے لگاتار کوشش کرتے رہنا چاہیے۔ کامیابی ان لوگوں کو ملتی ہے جو ہار نہیں مانتے۔"

tts = gTTS(text=text_ur, lang='ur')
tts.save("voice_ur.mp3")

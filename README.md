# 💖 Michi Dating Bot Clone (Telegram)

Yeh ek Telegram dating bot ka clone hai, jise **Python** aur **MongoDB** ka use karke banaya gaya hai. Yeh bot profile creation, matching, aur anonymous chat jaise features ko support karta hai, jaisa ki original Michelangelo bot mein hota hai.

## ✨ Features (मुख्य फीचर्स)

* **Complete Profile Flow:** User ka Naam, Gender, City, Age aur Photos ko step-by-step collect karta hai.
* **MongoDB Integration:** Sabhi user profiles ko MongoDB database mein surakshit (securely) save karta hai.
* **Anonymous Chat (Logic Ready):** Profile match hone ke baad users ko private aur anonymous chat mein connect karta hai.
* **Heroku Ready:** Aasan deployment ke liye `app.json` aur `Procfile` set kiye gaye hain.

## 🚀 Deployment (डिप्लॉयमेंट)

Aap is bot ko **Heroku** par aasaani se deploy kar sakte hain.

### One-Click Deploy (एक-क्लिक डिप्लॉय)

Neeche diye gaye **"Deploy to Heroku"** button par click karein. Yeh aapko Heroku par le jaayega jahan aapko sirf **BOT_TOKEN** aur **MONGO_URI** dalne honge.

[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/STD-DEEPANSHU/Dating)

> **IMPORTANT:** Upar diye gaye URL mein `YOUR_GITHUB_USERNAME` aur `YOUR_REPO_NAME` ko apne asal (actual) GitHub username aur Repository name se **zaroor change karein**.

### Manual Deployment (मैनुअल डिप्लॉयमेंट)

1.  **Repository Clone karein:**
    ```bash
    git clone [https://github.com/YOUR_GITHUB_USERNAME/YOUR_REPO_NAME.git](https://github.com/YOUR_GITHUB_USERNAME/YOUR_REPO_NAME.git)
    cd YOUR_REPO_NAME
    ```
2.  **Heroku CLI se Login karein.**
3.  **Heroku App banaayein:**
    ```bash
    heroku create <apna-app-ka-naam>
    ```
4.  **Environment Variables set karein:**
    ```bash
    heroku config:set BOT_TOKEN="<YOUR_BOT_TOKEN>"
    heroku config:set MONGO_URI="<YOUR_MONGO_CONNECTION_STRING>"
    ```
5.  **Deploy karein:**
    ```bash
    git push heroku master
    ```
6.  **Worker Dyno ko on karein:**
    ```bash
    heroku ps:scale worker=1
    ```

## ⚙️ Setup Requirements (ज़रूरी चीज़ें)

1.  **Telegram Bot Token:** **@BotFather** se apna Bot Token prapt karein.
2.  **MongoDB URI:** **MongoDB Atlas** se apna connection string (URI) generate karein.
3.  **Python 3.10+**

---

### 🌟 Agla Kadam (Next Step)

Ab aapka GitHub project **deployment ke liye ready** hai!

Humne abhi tak **Anonymous Chat** ka sirf basic logic discuss kiya hai, use poora **`bot.py`** mein integrate karna baaki hai, jismein **Profile Matching** aur **Chat Connection** ka kaam hoga.

Kya hum ab **Profile Matching** aur **Anonymous Chat** ka code pura karein?

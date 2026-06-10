"""
Jony Academy Learning Bot
- Placement Test (English/IELTS, Rus, Nemis, Turk)
- Vocabulary Flashcard + Quiz
"""
import os, json, sqlite3, random, html, logging
from telegram import (Update, InlineKeyboardButton, InlineKeyboardMarkup,
                      ReplyKeyboardMarkup, KeyboardButton)
from telegram.ext import (Application, CommandHandler, MessageHandler,
                          CallbackQueryHandler, ConversationHandler,
                          filters, ContextTypes)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

TOKEN = os.getenv("LEARNING_BOT_TOKEN", "YOUR_TOKEN_HERE")
DB    = "learning.db"

# ═══════════════════════════════════════════════════════════════════
#  DATABASE
# ═══════════════════════════════════════════════════════════════════
def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            uid      INTEGER PRIMARY KEY,
            name     TEXT,
            language TEXT,
            level    TEXT,
            joined   TEXT DEFAULT (date('now'))
        );
        CREATE TABLE IF NOT EXISTS quiz_progress (
            uid      INTEGER,
            lang     TEXT,
            word_id  TEXT,
            correct  INTEGER DEFAULT 0,
            wrong    INTEGER DEFAULT 0,
            PRIMARY KEY (uid, lang, word_id)
        );
        CREATE TABLE IF NOT EXISTS streaks (
            uid       INTEGER PRIMARY KEY,
            streak    INTEGER DEFAULT 0,
            last_date TEXT
        );
        """)

# ═══════════════════════════════════════════════════════════════════
#  PLACEMENT TEST DATA
# ═══════════════════════════════════════════════════════════════════
# Each question: (question_text, [options], correct_index, level_tag)
# level_tag: A1 A2 B1 B2 C1  → used to score final level

PLACEMENT = {
    "english": [
        # A1
        ("What ___ your name?", ["is", "are", "am", "be"], 0, "A1"),
        ("She ___ a teacher.", ["is", "are", "am", "be"], 0, "A1"),
        ("I ___ from Uzbekistan.", ["am", "is", "are", "be"], 0, "A1"),
        ("How ___ apples are there?", ["many", "much", "some", "any"], 0, "A1"),
        ("___ you speak English?", ["Can", "Do", "Are", "Is"], 0, "A1"),
        # A2
        ("She ___ to school every day.", ["goes", "go", "going", "went"], 0, "A2"),
        ("I ___ TV when she called.", ["was watching", "watch", "watches", "watched"], 0, "A2"),
        ("They ___ lunch yet.", ["haven't had", "didn't have", "don't have", "hasn't had"], 0, "A2"),
        ("___ is bigger — a cat or a dog?", ["Which", "What", "Who", "Whose"], 0, "A2"),
        ("He ___ to Paris last year.", ["travelled", "travels", "is travelling", "travel"], 0, "A2"),
        # B1
        ("If it rains, we ___ stay at home.", ["will", "would", "should", "shall"], 0, "B1"),
        ("She wishes she ___ more time.", ["had", "has", "have", "having"], 0, "B1"),
        ("The book ___ by Tolstoy.", ["was written", "wrote", "is writing", "writes"], 0, "B1"),
        ("Despite ___ tired, he continued working.", ["being", "to be", "be", "been"], 0, "B1"),
        ("He ___ here for three years.", ["has lived", "lived", "is living", "lives"], 0, "B1"),
        # B2
        ("Had she arrived earlier, she ___ the train.", ["would have caught", "would catch", "will catch", "catches"], 0, "B2"),
        ("The ___ data suggests economic growth.", ["latter", "latest", "last", "late"], 1, "B2"),
        ("She is ___ to the proposal.", ["opposed", "opposing", "opposes", "oppose"], 0, "B2"),
        ("The company's profits ___ significantly.", ["have surged", "surging", "surge", "surged"], 0, "B2"),
        # C1 / IELTS 6.5+
        ("The legislation was ___ to protect consumers.", ["enacted", "performed", "conducted", "executed"], 0, "C1"),
    ],

    "russian": [
        # A1
        ("Как вас ___?", ["зовут", "называют", "говорят", "пишут"], 0, "A1"),
        ("Это ___ книга.", ["моя", "мой", "моё", "мои"], 0, "A1"),
        ("Я ___ по-русски.", ["говорю", "говоришь", "говорит", "говорим"], 0, "A1"),
        ("___ тебя зовут?", ["Как", "Где", "Что", "Кто"], 0, "A1"),
        ("Он ___ студент.", ["—", "есть", "является", "был"], 0, "A1"),
        # A2
        ("Я ___ в Ташкент вчера.", ["приехал", "приеду", "приезжаю", "приезжал"], 0, "A2"),
        ("У меня ___ время.", ["нет", "не", "без", "нету"], 0, "A2"),
        ("Она ___ книгу каждый день.", ["читает", "читал", "читаю", "читают"], 0, "A2"),
        ("Мы ___ в кино завтра.", ["пойдём", "идём", "шли", "пошли"], 0, "A2"),
        ("Это ___ город?", ["чей", "чьё", "чья", "чьи"], 0, "A2"),
        # B1
        ("Если бы я ___ время, я бы помог.", ["имел", "имею", "буду иметь", "имеющий"], 0, "B1"),
        ("Книга ___ на столе.", ["лежит", "лежат", "лежу", "лежишь"], 0, "B1"),
        ("Он работает, ___ устал.", ["хотя", "потому что", "чтобы", "если"], 0, "B1"),
        ("Это задание было ___ выполнено.", ["правильно", "правильный", "правильна", "правильное"], 0, "B1"),
        ("Чем больше ты читаешь, тем ___ знаешь.", ["больше", "меньше", "лучше", "хуже"], 0, "B1"),
        # B2
        ("Несмотря на ___ погоду, мы вышли гулять.", ["плохую", "плохой", "плохое", "плохим"], 0, "B2"),
        ("Это решение ___ всеми участниками.", ["было принято", "принято было", "приняло", "принимает"], 0, "B2"),
        ("Вряд ли он ___ на это согласится.", ["когда-либо", "никогда", "всегда", "иногда"], 0, "B2"),
        ("Данный закон ___ в 2020 году.", ["вступил в силу", "выступил в силу", "вошёл силу", "стал силу"], 0, "B2"),
        ("Судя по всему, ситуация ___ нормализоваться.", ["начинает", "начала", "начнёт", "начинала"], 0, "B2"),
    ],

    "german": [
        # A1
        ("Wie ___ Sie?", ["heißen", "heißt", "heiße", "heißen"], 0, "A1"),
        ("Ich ___ aus Usbekistan.", ["komme", "kommt", "kommen", "kommst"], 0, "A1"),
        ("Das ist ___ Buch.", ["ein", "eine", "einen", "einem"], 0, "A1"),
        ("___ ist das?", ["Was", "Wer", "Wie", "Wo"], 0, "A1"),
        ("Ich ___ Tee.", ["trinke", "trinkt", "trinken", "trinkst"], 0, "A1"),
        # A2
        ("Gestern ___ ich ins Kino gegangen.", ["bin", "habe", "war", "wurde"], 0, "A2"),
        ("Sie ___ jeden Tag Deutsch.", ["lernt", "lernte", "gelernt", "lerne"], 0, "A2"),
        ("Ich ___ morgen arbeiten.", ["muss", "musste", "müssen", "müsst"], 0, "A2"),
        ("___ Hund ist das?", ["Wessen", "Welcher", "Was", "Wer"], 0, "A2"),
        ("Er ist ___ als sie.", ["größer", "groß", "großer", "am größten"], 0, "A2"),
        # B1
        ("Wenn ich Zeit ___, würde ich mehr lesen.", ["hätte", "habe", "hatte", "haben"], 0, "B1"),
        ("Das Buch ___ von Goethe geschrieben.", ["wurde", "wird", "worden", "war"], 0, "B1"),
        ("___ du kommst, ruf mich an.", ["Bevor", "Nachdem", "Obwohl", "Weil"], 0, "B1"),
        ("Er hat versprochen, ___ zu kommen.", ["pünktlich", "pünktliche", "pünktlichem", "pünktlicher"], 0, "B1"),
        ("Das ___ Problem ist die Zeit.", ["größte", "größten", "großes", "großem"], 0, "B1"),
        # B2
        ("Das Projekt ___ bis Ende des Jahres fertiggestellt werden.", ["soll", "solle", "sollte", "sollen"], 0, "B2"),
        ("___ seiner ErscN[�pfung arbeitete er weiter.", ["Trotz", "Wegen", "Durch", "Mit"], 0, "B2"),
        ("Die Ergebnisse ___ auf eine positive Entwicklung hin.", ["deuten", "deutet", "deutete", "gedeutet"], 0, "B2"),
        ("Es ist ___, dass alle Beteiligten informiert werden.", ["unerlässlich", "unnötig", "unwichtig", "unklar"], 0, "B2"),
        ("Die Maßnahmen wurden ___ umgesetzt.", ["konsequent", "konsequente", "konsequentere", "am konsequentesten"], 0, "B2"),
    ],

    "turkish": [
        # A1
        ("Adın ___ ne?", ["senin", "benim", "onun", "bizim"], 0, "A1"),
        ("Ben Türkçe ___.", ["öğreniyorum", "öğreniyor", "öğreniyorsun", "öğreniyoruz"], 0, "A1"),
        ("Bu ___ bir kalem.", ["benim", "senin", "onun", "onların"], 0, "A1"),
        ("Merhaba, nasıl ___?", ["sınız", "sın", "sın", "sız"], 0, "A1"),
        ("O bir ___.", ["öğrenci", "öğrencim", "öğrencisin", "öğrenciyim"], 0, "A1"),
        # A2
        ("Dün okula ___ gittim.", ["en yavaş", "en hızlı", "yavaşça", "hızlıca"], 2, "A2"),
        ("Arkadaşım bana yardım ___.", ["etti", "etmedi", "edecek", "ediyor"], 0, "A2"),
        ("Sabahleyin kahve ___ içerim.", ["genellikle", "bazen", "hiç", "nadiren"], 0, "A2"),
        ("Bu kitabı ___ okudun mu?", ["henüz", "hiç", "artık", "zaten"], 1, "B1"),
        ("Yarın hava güzel ___ çıkarım.", ["olursa", "oldu", "olmuş", "olsun"], 0, "B1"),
        # B1
        ("Eğer erken ___, trene yetişirdin.", ["kalksaydın", "kalksan", "kalktıysan", "kalkacaksan"], 0, "B1"),
        ("Bu konu hakkında ___ bilgim yok.", ["hiçbir", "bir", "bazı", "her"], 0, "B1"),
        ("Proje ___ tamamlanacak.", ["zamanında", "zamanlı", "zamanından", "zamansız"], 0, "B1"),
        ("Çalışmak ___ başarıya ulaşmak mümkündür.", ["sayesinde", "rağmen", "dolayısıyla", "kadar"], 0, "B1"),
        ("Ne kadar çok okursan, o kadar çok ___.", ["öğrenirsin", "öğrendin", "öğrenecektin", "öğrenmiş"], 0, "B1"),
        # B2
        ("Bu yasa, tüketicileri korumak amacıyla ___.", ["yürürlüğe girdi", "yürürlüğe çıktı", "yürürlükten kalktı", "yürürlükte değil"], 0, "B2"),
        ("Sonuçlar, olumlu bir gelişmeye ___ işaret ediyor.", ["açıkça", "kapalıca", "belirsizce", "kesinlikle"], 0, "B2"),
        ("Tüm katılımcıların ___ edilmesi zorunludur.", ["bilgilendirilmesi", "bilgilenmesi", "bilgilendirmesi", "bilgileniyor"], 0, "B2"),
        ("Alınan önlemler ___ hayata geçirildi.", ["kararlılıkla", "kararlılık", "kararlıca", "kararsızca"], 0, "B2"),
        ("Durum ne olursa olsun, ___ devam edeceğiz.", ["çalışmaya", "çalışma", "çalışarak", "çalışmadan"], 0, "B2"),
    ],
}

# ═══════════════════════════════════════════════════════════════════
#  VOCABULARY DATA
# ═══════════════════════════════════════════════════════════════════
# Format: {lang: {level: [ {id, word, translation, example}, ... ] }}

VOCAB = {
    "english": {
        "A1": [
            {"id":"en_a1_1","word":"Happy","translation":"Xursand","example":"I am happy today. (Bugun xursandman.)"},
            {"id":"en_a1_2","word":"Beautiful","translation":"Chiroyli","example":"She is beautiful. (U chiroyli.)"},
            {"id":"en_a1_3","word":"Friend","translation":"Do'st","example":"He is my friend. (U mening do'stim.)"},
            {"id":"en_a1_4","word":"School","translation":"Maktab","example":"I go to school. (Men maktabga boraman.)"},
            {"id":"en_a1_5","word":"Water","translation":"Suv","example":"I drink water. (Men suv ichaman.)"},
            {"id":"en_a1_6","word":"House","translation":"Uy","example":"This is my house. (Bu mening uyim.)"},
            {"id":"en_a1_7","word":"Book","translation":"Kitob","example":"I read a book. (Men kitob o'qiyman.)"},
            {"id":"en_a1_8","word":"Family","translation":"Oila","example":"My family is big. (Mening oilam katta.)"},
        ],
        "A2": [
            {"id":"en_a2_1","word":"Improve","translation":"Yaxshilamoq","example":"I want to improve my English."},
            {"id":"en_a2_2","word":"Describe","translation":"Tasvirlamoq","example":"Can you describe the picture?"},
            {"id":"en_a2_3","word":"Explain","translation":"Tushuntirmoq","example":"Please explain the rule."},
            {"id":"en_a2_4","word":"Journey","translation":"Sayohat","example":"The journey took two hours."},
            {"id":"en_a2_5","word":"Culture","translation":"Madaniyat","example":"Every country has its own culture."},
            {"id":"en_a2_6","word":"Compare","translation":"Taqqoslamoq","example":"Compare these two sentences."},
            {"id":"en_a2_7","word":"Opinion","translation":"Fikr","example":"In my opinion, it is correct."},
            {"id":"en_a2_8","word":"Environment","translation":"Muhit / Atrof-muhit","example":"We must protect the environment."},
        ],
        "B1": [
            {"id":"en_b1_1","word":"Significant","translation":"Muhim, sezilarli","example":"There was a significant improvement."},
            {"id":"en_b1_2","word":"Contribute","translation":"Hissa qo'shmoq","example":"She contributes to the project."},
            {"id":"en_b1_3","word":"Consequence","translation":"Oqibat","example":"Think about the consequences."},
            {"id":"en_b1_4","word":"Diverse","translation":"Xilma-xil, turli","example":"The city has a diverse population."},
            {"id":"en_b1_5","word":"Achieve","translation":"Erishmoq","example":"He achieved his goal."},
            {"id":"en_b1_6","word":"Reliable","translation":"Ishonchli","example":"She is a reliable person."},
            {"id":"en_b1_7","word":"Maintain","translation":"Saqlash, qo'llab-quvvatlash","example":"We must maintain standards."},
            {"id":"en_b1_8","word":"Sufficient","translation":"Yetarli","example":"Is the time sufficient?"},
        ],
        "B2": [
            {"id":"en_b2_1","word":"Inevitable","translation":"Muqarrar","example":"Change is inevitable."},
            {"id":"en_b2_2","word":"Scrutinize","translation":"Sinchkovlik bilan tekshirmoq","example":"The data was scrutinized."},
            {"id":"en_b2_3","word":"Fluctuate","translation":"Tebranmoq, o'zgarmoq","example":"Prices fluctuate daily."},
            {"id":"en_b2_4","word":"Ambiguous","translation":"Noaniq, ikki ma'noli","example":"The statement was ambiguous."},
            {"id":"en_b2_5","word":"Advocacy","translation":"Himoya, yoqlash","example":"She works in advocacy for rights."},
            {"id":"en_b2_6","word":"Consolidate","translation":"Mustahkamlash","example":"Let's consolidate our knowledge."},
            {"id":"en_b2_7","word":"Empirical","translation":"Empirik, tajribaviy","example":"We need empirical evidence."},
            {"id":"en_b2_8","word":"Comprehensive","translation":"To'liq, keng qamrovli","example":"A comprehensive study was done."},
        ],
    },
    "russian": {
        "A1": [
            {"id":"ru_a1_1","word":"Привет","translation":"Salom","example":"Привет! Как дела? (Salom! Qandaysiz?)"},
            {"id":"ru_a1_2","word":"Спасибо","translation":"Rahmat","example":"Спасибо за помощь. (Yordam uchun rahmat.)"},
            {"id":"ru_a1_3","word":"Книга","translation":"Kitob","example":"Это интересная книга. (Bu qiziqarli kitob.)"},
            {"id":"ru_a1_4","word":"Школа","translation":"Maktab","example":"Я иду в школу. (Men maktabga boraman.)"},
            {"id":"ru_a1_5","word":"Друг","translation":"Do'st","example":"Он мой лучший друг. (U mening eng yaxshi do'stim.)"},
            {"id":"ru_a1_6","word":"Работа","translation":"Ish / Mehnat","example":"Я иду на работу. (Men ishga boraman.)"},
            {"id":"ru_a1_7","word":"Время","translation":"Vaqt","example":"У меня нет времени. (Menda vaqt yo'q.)"},
            {"id":"ru_a1_8","word":"Город","translation":"Shahar","example":"Это красивый город. (Bu chiroyli shahar.)"},
        ],
        "B1": [
            {"id":"ru_b1_1","word":"Возможность","translation":"Imkoniyat","example":"У меня есть возможность учиться."},
            {"id":"ru_b1_2","word":"Развитие","translation":"Rivojlanish","example":"Развитие страны важно."},
            {"id":"ru_b1_3","word":"Обсуждение","translation":"Muhokama","example":"На встрече было обсуждение."},
            {"id":"ru_b1_4","word":"Достижение","translation":"Yutuq","example":"Это большое достижение."},
            {"id":"ru_b1_5","word":"Влияние","translation":"Ta'sir","example":"Климат влияет на жизнь."},
        ],
    },
    "german": {
        "A1": [
            {"id":"de_a1_1","word":"Hallo","translation":"Salom","example":"Hallo! Wie geht es Ihnen? (Salom! Yaxshimisiz?)"},
            {"id":"de_a1_2","word":"Danke","translation":"Rahmat","example":"Danke für Ihre Hilfe. (Yordamingiz uchun rahmat.)"},
            {"id":"de_a1_3","word":"Schule","translation":"Maktab","example":"Ich gehe in die Schule. (Men maktabga boraman.)"},
            {"id":"de_a1_4","word":"Freund","translation":"Do'st","example":"Er ist mein bester Freund. (U mening eng yaxshi do'stim.)"},
            {"id":"de_a1_5","word":"Haus","translation":"Uy","example":"Das ist mein Haus. (Bu mening uyim.)"},
            {"id":"de_a1_6","word":"Arbeit","translation":"Ish","example":"Ich gehe zur Arbeit. (Men ishga boraman.)"},
            {"id":"de_a1_7","word":"Zeit","translation":"Vaqt","example":"Ich habe keine Zeit. (Menda vaqt yo'q.)"},
            {"id":"de_a1_8","word":"Stadt","translation":"Shahar","example":"Das ist eine schöne Stadt. (Bu chiroyli shahar.)"},
        ],
        "B1": [
            {"id":"de_b1_1","word":"Möglichkeit","translation":"Imkoniyat","example":"Ich habe die Möglichkeit zu lernen."},
            {"id":"de_b1_2","word":"Entwicklung","translation":"Rivojlanish","example":"Die Entwicklung des Landes ist wichtig."},
            {"id":"de_b1_3","word":"Erfahrung","translation":"Tajriba","example":"Ich habe viel Erfahrung."},
            {"id":"de_b1_4","word":"Entscheidung","translation":"Qaror","example":"Das war eine gute Entscheidung."},
            {"id":"de_b1_5","word":"Verantwortung","translation":"Mas'uliyat","example":"Das ist meine Verantwortung."},
        ],
    },
    "turkish": {
        "A1": [
            {"id":"tr_a1_1","word":"Merhaba","translation":"Salom","example":"Merhaba! Nasılsınız? (Salom! Yaxshimisiz?)"},
            {"id":"tr_a1_2","word":"Teşekkürler","translation":"Rahmat","example":"Yardımınız için teşekkürler. (Yordamingiz uchun rahmat.)"},
            {"id":"tr_a1_3","word":"Okul","translation":"Maktab","example":"Okula gidiyorum. (Men maktabga boraman.)"},
            {"id":"tr_a1_4","word":"Arkadaş","translation":"Do'st","example":"O benim arkadaşım. (U mening do'stim.)"},
            {"id":"tr_a1_5","word":"Ev","translation":"Uy","example":"Bu benim evim. (Bu mening uyim.)"},
            {"id":"tr_a1_6","word":"Çalışmak","translation":"Ishlash / O'qish","example":"Her gün çalışıyorum. (Har kuni ishlayman.)"},
            {"id":"tr_a1_7","word":"Zaman","translation":"Vaqt","example":"Zamanım yok. (Menda vaqt yo'q.)"},
            {"id":"tr_a1_8","word":"Şehir","translation":"Shahar","example":"Bu güzel bir şehir. (Bu chiroyli shahar.)"},
        ],
        "B1": [
            {"id":"tr_b1_1","word":"Fırsat","translation":"Imkoniyat","example":"Bu harika bir fırsat."},
            {"id":"tr_b1_2","word":"Gelişim","translation":"Rivojlanish","example":"Kişisel gelişim önemlidir."},
            {"id":"tr_b1_3","word":"Deneyim","translation":"Tajriba","example":"Çok deneyimim var."},
            {"id":"tr_b1_4","word":"Karar","translation":"Qaror","example":"Bu doğru bir karar."},
            {"id":"tr_b1_5","word":"Sorumluluk","translation":"Mas'uliyat","example":"Bu benim sorumluluğum."},
        ],
    },
}

# ═══════════════════════════════════════════════════════════════════
#  CONVERSATION STATES
# ═══════════════════════════════════════════════════════════════════
(MAIN_MENU, LANG_SELECT,
 TEST_RUNNING,
 VOCAB_MENU, VOCAB_FLASH, VOCAB_QUIZ) = range(6)

LANG_NAMES = {
    "english": "🇬🇧 Ingliz tili / IELTS",
    "russian": "🇷🇺 Rus tili",
    "german":  "🇩🇪 Nemis tili",
    "turkish": "🇹🇷 Turk tili",
}

LEVEL_SCORE = {  # pct thresholds
    "english": [(0, "A1"), (0.30, "A2"), (0.55, "B1"), (0.75, "B2"), (0.90, "C1")],
    "russian":  [(0, "A1"), (0.30, "A2"), (0.55, "B1"), (0.75, "B2"), (0.90, "C1")],
    "german":   [(0, "A1"), (0.30, "A2"), (0.55, "B1"), (0.75, "B2"), (0.90, "C1")],
    "turkish":  [(0, "A1"), (0.30, "A2"), (0.55, "B1"), (0.75, "B2"), (0.90, "C1")],
}

def get_level(lang, correct, total):
    pct = correct / total if total else 0
    lvl = "A1"
    for threshold, label in LEVEL_SCORE[lang]:
        if pct >= threshold:
            lvl = label
    return lvl

def main_menu_kb():
    return ReplyKeyboardMarkup(
        [["📝 Placement Test", "📚 Lug'at o'rganish"],
         ["📊 Mening natijalarim", "ℹ️ Yordam"]],
        resize_keyboard=True
    )

def lang_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇬🇧 Ingliz / IELTS", callback_data="lang_english")],
        [InlineKeyboardButton("🇷🇺 Rus tili",        callback_data="lang_russian")],
        [InlineKeyboardButton("🇩🇪 Nemis tili",       callback_data="lang_german")],
        [InlineKeyboardButton("🇹🇷 Turk tili",        callback_data="lang_turkish")],
    ])

# ═══════════════════════════════════════════════════════════════════
#  /start
# ═══════════════════════════════════════════════════════════════════
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    name = update.effective_user.first_name or "O'quvchi"
    with db() as con:
        con.execute("INSERT OR IGNORE INTO users(uid,name) VALUES(?,?)", (uid, name))
    await update.message.reply_text(
        f"🎓 <b>Jony Academy Learning Bot</b>\n\n"
        f"Assalomu alaykum, <b>{html.escape(name)}</b>!\n\n"
        f"Bu bot orqali:\n"
        f"• <b>Placement Test</b> — darajangizni aniqlang\n"
        f"• <b>Lug'at</b> — Flashcard va Quiz bilan so'z o'rganing\n"
        f"• <b>4 ta til</b>: Ingliz, Rus, Nemis, Turk\n\n"
        f"Pastdagi tugmalardan birini tanlang 👇",
        parse_mode="HTML",
        reply_markup=main_menu_kb()
    )
    return MAIN_MENU

# ═══════════════════════════════════════════════════════════════════
#  PLACEMENT TEST FLOW
# ═══════════════════════════════════════════════════════════════════
async def start_placement(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📝 <b>Placement Test</b>\n\nQaysi tilda test topshirmoqchisiz?",
        parse_mode="HTML",
        reply_markup=lang_kb()
    )
    return LANG_SELECT

async def lang_chosen_test(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = query.data.replace("lang_", "")
    ctx.user_data["test_lang"]     = lang
    ctx.user_data["test_questions"]= list(PLACEMENT[lang])  # copy
    ctx.user_data["test_index"]    = 0
    ctx.user_data["test_correct"]  = 0
    ctx.user_data["test_wrong"]    = []
    await query.edit_message_text(
        f"✅ <b>{LANG_NAMES[lang]}</b> tanlandi!\n\n"
        f"📋 {len(PLACEMENT[lang])} ta savol\n"
        f"⏱ ~5 daqiqa\n\n"
        f"Birinchi savolga tayyor bo'ling!",
        parse_mode="HTML"
    )
    await send_question(update, ctx, via_query=True)
    return TEST_RUNNING

async def send_question(update, ctx, via_query=False):
    idx = ctx.user_data["test_index"]
    qs  = ctx.user_data["test_questions"]
    if idx >= len(qs):
        await finish_test(update, ctx)
        return

    q, opts, correct, lvl = qs[idx]
    ctx.user_data["test_current_correct"] = correct

    # shuffle options but keep track of correct answer text
    pairs = list(enumerate(opts))
    random.shuffle(pairs)
    ctx.user_data["test_shuffled_correct"] = None
    shuffled = []
    for new_i, (orig_i, opt) in enumerate(pairs):
        shuffled.append(opt)
        if orig_i == correct:
            ctx.user_data["test_shuffled_correct"] = new_i

    buttons = [
        [InlineKeyboardButton(f"{['A','B','C','D'][i]}. {o}",
                              callback_data=f"ans_{i}")]
        for i, o in enumerate(shuffled)
    ]
    ctx.user_data["test_opts"] = shuffled
    text = (f"❓ <b>Savol {idx+1}/{len(qs)}</b>\n\n"
            f"<i>{html.escape(q)}</i>")
    if via_query:
        chat_id = update.callback_query.message.chat_id
        await ctx.bot.send_message(chat_id, text, parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await update.message.reply_text(text, parse_mode="HTML",
                                        reply_markup=InlineKeyboardMarkup(buttons))

async def test_answer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chosen = int(query.data.replace("ans_", ""))
    correct = ctx.user_data["test_shuffled_correct"]
    opts    = ctx.user_data["test_opts"]

    if chosen == correct:
        ctx.user_data["test_correct"] += 1
        fb = "✅ To'g'ri!"
    else:
        ctx.user_data["test_wrong"].append(ctx.user_data["test_index"])
        fb = f"❌ Noto'g'ri. To'g'ri javob: <b>{html.escape(opts[correct])}</b>"

    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text(fb, parse_mode="HTML")

    ctx.user_data["test_index"] += 1
    await send_question(update, ctx, via_query=True)
    return TEST_RUNNING

async def finish_test(update, ctx):
    lang    = ctx.user_data["test_lang"]
    correct = ctx.user_data["test_correct"]
    total   = len(ctx.user_data["test_questions"])
    pct     = round(correct / total * 100)
    level   = get_level(lang, correct, total)
    uid     = update.callback_query.from_user.id

    with db() as con:
        con.execute("UPDATE users SET language=?, level=? WHERE uid=?",
                    (lang, level, uid))

    ielts_map = {"A1":"3.0","A2":"4.0","B1":"5.0","B2":"6.0","C1":"7.0+"}
    extra = (f"\n🎯 IELTS ekvivalenti: <b>{ielts_map.get(level,'—')}</b>"
             if lang == "english" else "")

    await update.callback_query.message.reply_text(
        f"🏆 <b>Test yakunlandi!</b>\n\n"
        f"📊 Natija: <b>{correct}/{total}</b> ({pct}%)\n"
        f"🎓 Darajangiz: <b>{level}</b>{extra}\n\n"
        f"Endi <b>Lugat organish</b> bolimiga oting 👇",
        parse_mode="HTML",
        reply_markup=main_menu_kb()
    )
    return MAIN_MENU

# ═══════════════════════════════════════════════════════════════════
#  VOCAB FLASHCARD + QUIZ
# ═══════════════════════════════════════════════════════════════════
async def start_vocab(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    with db() as con:
        row = con.execute("SELECT language, level FROM users WHERE uid=?", (uid,)).fetchone()

    if not row or not row["language"]:
        await update.message.reply_text(
            "📚 <b>Lug'at o'rganish</b>\n\nAvval til tanlang:",
            parse_mode="HTML",
            reply_markup=lang_kb()
        )
        ctx.user_data["vocab_after_lang"] = True
        return LANG_SELECT

    lang  = row["language"]
    level = row["level"] or "A1"
    ctx.user_data["vocab_lang"]  = lang
    ctx.user_data["vocab_level"] = level
    await show_vocab_menu(update, ctx, lang, level)
    return VOCAB_MENU

async def lang_chosen_vocab(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = query.data.replace("lang_", "")
    ctx.user_data["vocab_lang"]  = lang
    ctx.user_data["vocab_level"] = "A1"
    uid = query.from_user.id
    with db() as con:
        con.execute("UPDATE users SET language=? WHERE uid=?", (lang, uid))
    await query.edit_message_text(f"✅ {LANG_NAMES[lang]} tanlandi!")
    fake_upd = type('FU', (), {'message': query.message, 'effective_user': query.from_user})()
    await show_vocab_menu(fake_upd, ctx, lang, "A1")
    return VOCAB_MENU

async def show_vocab_menu(update, ctx, lang, level):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🃏 Flashcard", callback_data="flash_start"),
         InlineKeyboardButton("🧩 Quiz",      callback_data="quiz_start")],
        [InlineKeyboardButton("📈 Progressim", callback_data="vocab_progress")],
    ])
    await update.message.reply_text(
        f"📚 <b>Lug'at o'rganish</b>\n\n"
        f"Til: {LANG_NAMES[lang]}\n"
        f"Daraja: <b>{level}</b>\n\n"
        f"Qanday rejimda o'rganmoqchisiz?",
        parse_mode="HTML",
        reply_markup=kb
    )

async def flash_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang  = ctx.user_data.get("vocab_lang", "english")
    level = ctx.user_data.get("vocab_level", "A1")

    words = VOCAB.get(lang, {}).get(level) or VOCAB.get(lang, {}).get("A1", [])
    if not words:
        await query.edit_message_text("Hozircha bu daraja uchun so'zlar yo'q.")
        return VOCAB_MENU

    random.shuffle(words)
    ctx.user_data["flash_words"] = words
    ctx.user_data["flash_idx"]   = 0
    ctx.user_data["flash_shown"] = False
    await send_flashcard(query, ctx)
    return VOCAB_FLASH

async def send_flashcard(query_or_msg, ctx, edit=True):
    words = ctx.user_data["flash_words"]
    idx   = ctx.user_data["flash_idx"]
    shown = ctx.user_data.get("flash_shown", False)

    if idx >= len(words):
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔄 Qaytadan", callback_data="flash_restart"),
            InlineKeyboardButton("🏠 Menyu",    callback_data="vocab_menu"),
        ]])
        txt = "🎉 <b>Barcha kartochkalar ko'rib chiqildi!</b>\n\nQuizga o'ting yoki qaytadan mashq qiling."
        if edit:
            await query_or_msg.edit_message_text(txt, parse_mode="HTML", reply_markup=kb)
        return

    w = words[idx]
    if not shown:
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("👁 Tarjimani ko'rish", callback_data="flash_reveal"),
        ]])
        txt = (f"🃏 <b>Flashcard {idx+1}/{len(words)}</b>\n\n"
               f"<b>{html.escape(w['word'])}</b>\n\n"
               f"<i>Tarjimasini bilasizmi?</i>")
    else:
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Bildim", callback_data="flash_know"),
            InlineKeyboardButton("❌ Bilmadim", callback_data="flash_dontknow"),
        ]])
        txt = (f"🃏 <b>Flashcard {idx+1}/{len(words)}</b>\n\n"
               f"<b>{html.escape(w['word'])}</b>\n"
               f"➜ <b>{html.escape(w['translation'])}</b>\n\n"
               f"📝 <i>{html.escape(w['example'])}</i>")

    if edit:
        await query_or_msg.edit_message_text(txt, parse_mode="HTML", reply_markup=kb)

async def flash_reveal(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data["flash_shown"] = True
    await send_flashcard(query, ctx)
    return VOCAB_FLASH

async def flash_know(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Zo'r! +1 ✅")
    uid = query.from_user.id
    w   = ctx.user_data["flash_words"][ctx.user_data["flash_idx"]]
    lang = ctx.user_data.get("vocab_lang", "english")
    with db() as con:
        con.execute("""INSERT INTO quiz_progress(uid,lang,word_id,correct)
                       VALUES(?,?,?,1)
                       ON CONFLICT(uid,lang,word_id)
                       DO UPDATE SET correct=correct+1""",
                    (uid, lang, w["id"]))
    ctx.user_data["flash_idx"]   += 1
    ctx.user_data["flash_shown"]  = False
    await send_flashcard(query, ctx)
    return VOCAB_FLASH

async def flash_dontknow(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Keyingi safar bilasiz! 💪")
    uid = query.from_user.id
    w   = ctx.user_data["flash_words"][ctx.user_data["flash_idx"]]
    lang = ctx.user_data.get("vocab_lang", "english")
    with db() as con:
        con.execute("""INSERT INTO quiz_progress(uid,lang,word_id,wrong)
                       VALUES(?,?,?,1)
                       ON CONFLICT(uid,lang,word_id)
                       DO UPDATE SET wrong=wrong+1""",
                    (uid, lang, w["id"]))
    ctx.user_data["flash_idx"]   += 1
    ctx.user_data["flash_shown"]  = False
    await send_flashcard(query, ctx)
    return VOCAB_FLASH

async def flash_restart(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    words = ctx.user_data["flash_words"]
    random.shuffle(words)
    ctx.user_data["flash_words"] = words
    ctx.user_data["flash_idx"]   = 0
    ctx.user_data["flash_shown"] = False
    await send_flashcard(query, ctx)
    return VOCAB_FLASH

# ── QUIZ ──────────────────────────────────────────────────────────
async def quiz_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang  = ctx.user_data.get("vocab_lang", "english")
    level = ctx.user_data.get("vocab_level", "A1")

    words = VOCAB.get(lang, {}).get(level) or VOCAB.get(lang, {}).get("A1", [])
    if len(words) < 4:
        await query.edit_message_text("Quiz uchun kamida 4 ta so'z kerak.")
        return VOCAB_MENU

    random.shuffle(words)
    ctx.user_data["quiz_words"]   = words
    ctx.user_data["quiz_idx"]     = 0
    ctx.user_data["quiz_correct"] = 0
    await send_quiz_q(query, ctx)
    return VOCAB_QUIZ

async def send_quiz_q(query, ctx):
    words = ctx.user_data["quiz_words"]
    idx   = ctx.user_data["quiz_idx"]

    if idx >= len(words):
        correct = ctx.user_data["quiz_correct"]
        total   = len(words)
        pct     = round(correct/total*100)
        msg = (f"🎯 <b>Quiz yakunlandi!</b>\n\n"
               f"Natija: <b>{correct}/{total}</b> ({pct}%)\n"
               f"{'Ajoyib! 🌟' if pct>=80 else 'Yaxshi! 💪' if pct>=50 else 'Koproq mashq qiling! 📖'}")
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔄 Qaytadan", callback_data="quiz_restart"),
            InlineKeyboardButton("🃏 Flashcard", callback_data="flash_start"),
        ]])
        await query.edit_message_text(msg, parse_mode="HTML", reply_markup=kb)
        return

    w = words[idx]
    # generate 3 wrong options from other words
    others = [x for x in words if x["id"] != w["id"]]
    wrong3 = random.sample(others, min(3, len(others)))
    options = [w["translation"]] + [x["translation"] for x in wrong3]
    random.shuffle(options)
    correct_idx = options.index(w["translation"])
    ctx.user_data["quiz_correct_idx"] = correct_idx

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{['A','B','C','D'][i]}. {o}", callback_data=f"qans_{i}")]
        for i, o in enumerate(options)
    ])
    txt = (f"🧩 <b>Quiz {idx+1}/{len(words)}</b>\n\n"
           f"<b>{html.escape(w['word'])}</b> — tarjimasi?")
    await query.edit_message_text(txt, parse_mode="HTML", reply_markup=kb)

async def quiz_answer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chosen  = int(query.data.replace("qans_", ""))
    correct = ctx.user_data["quiz_correct_idx"]
    words   = ctx.user_data["quiz_words"]
    idx     = ctx.user_data["quiz_idx"]
    w       = words[idx]

    if chosen == correct:
        ctx.user_data["quiz_correct"] += 1
        await query.answer("✅ To'g'ri!", show_alert=False)
    else:
        await query.answer(f"❌ To'g'ri: {w['translation']}", show_alert=True)

    ctx.user_data["quiz_idx"] += 1
    await send_quiz_q(query, ctx)
    return VOCAB_QUIZ

async def quiz_restart(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    words = ctx.user_data["quiz_words"]
    random.shuffle(words)
    ctx.user_data["quiz_words"]   = words
    ctx.user_data["quiz_idx"]     = 0
    ctx.user_data["quiz_correct"] = 0
    await send_quiz_q(query, ctx)
    return VOCAB_QUIZ

async def vocab_menu_back(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang  = ctx.user_data.get("vocab_lang","english")
    level = ctx.user_data.get("vocab_level","A1")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🃏 Flashcard", callback_data="flash_start"),
         InlineKeyboardButton("🧩 Quiz",      callback_data="quiz_start")],
        [InlineKeyboardButton("📈 Progressim", callback_data="vocab_progress")],
    ])
    await query.edit_message_text(
        f"📚 <b>Lug'at o'rganish</b>\n\nTil: {LANG_NAMES[lang]}\nDaraja: <b>{level}</b>",
        parse_mode="HTML", reply_markup=kb
    )
    return VOCAB_MENU

# ═══════════════════════════════════════════════════════════════════
#  STATS
# ═══════════════════════════════════════════════════════════════════
async def show_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    with db() as con:
        user = con.execute("SELECT * FROM users WHERE uid=?", (uid,)).fetchone()
        prog = con.execute(
            "SELECT SUM(correct) as c, SUM(wrong) as w FROM quiz_progress WHERE uid=?",
            (uid,)).fetchone()
    if not user:
        await update.message.reply_text("Avval /start bosing!")
        return MAIN_MENU

    lang  = LANG_NAMES.get(user["language"], "—") if user["language"] else "—"
    level = user["level"] or "—"
    c     = prog["c"] or 0
    w     = prog["w"] or 0
    total = c + w
    acc   = round(c/total*100) if total else 0

    await update.message.reply_text(
        f"📊 <b>Mening natijalarim</b>\n\n"
        f"👤 Ism: {html.escape(user['name'] or '')}\n"
        f"🌍 Til: {lang}\n"
        f"🎓 Daraja: <b>{level}</b>\n\n"
        f"📚 Jami o'rganilgan so'zlar: <b>{total}</b>\n"
        f"✅ To'g'ri: <b>{c}</b>   ❌ Noto'g'ri: <b>{w}</b>\n"
        f"🎯 Aniqlik: <b>{acc}%</b>\n\n"
        f"Davom eting! 💪",
        parse_mode="HTML",
        reply_markup=main_menu_kb()
    )
    return MAIN_MENU

async def show_progress_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    with db() as con:
        prog = con.execute(
            "SELECT SUM(correct) as c, SUM(wrong) as w FROM quiz_progress WHERE uid=?",
            (uid,)).fetchone()
    c = prog["c"] or 0
    w = prog["w"] or 0
    total = c + w
    acc = round(c/total*100) if total else 0
    await query.edit_message_text(
        f"📈 <b>Progressingiz</b>\n\n"
        f"Jami so'zlar: <b>{total}</b>\n"
        f"✅ To'g'ri: <b>{c}</b>\n"
        f"❌ Noto'g'ri: <b>{w}</b>\n"
        f"🎯 Aniqlik: <b>{acc}%</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Orqaga", callback_data="vocab_menu")
        ]])
    )
    return VOCAB_MENU

# ═══════════════════════════════════════════════════════════════════
#  HELP
# ═══════════════════════════════════════════════════════════════════
async def show_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ <b>Yordam</b>\n\n"
        "📝 <b>Placement Test</b>\n"
        "20 ta savol orqali til darajangiz aniqlanadi.\n\n"
        "🃏 <b>Flashcard</b>\n"
        "So'z ko'rinadi → tarjimasini o'ylang → tekshiring → bildim/bilmadim.\n\n"
        "🧩 <b>Quiz</b>\n"
        "So'zga 4 ta tarjima beriladi → to'g'risini tanlang.\n\n"
        "📊 <b>Natijalar</b>\n"
        "Daraja, to'g'ri/noto'g'ri javoblar statistikasi.\n\n"
        "🆘 Muammo bo'lsa: @Jony_Academy_admin",
        parse_mode="HTML",
        reply_markup=main_menu_kb()
    )
    return MAIN_MENU

# ═══════════════════════════════════════════════════════════════════
#  FALLBACK
# ═══════════════════════════════════════════════════════════════════
async def fallback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Tugmalardan foydalaning 👇",
        reply_markup=main_menu_kb()
    )
    return MAIN_MENU

# ═══════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════
def main():
    init_db()
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start)],
        states={
            MAIN_MENU: [
                MessageHandler(filters.Regex("^📝 Placement Test$"), start_placement),
                MessageHandler(filters.Regex("^📚 Lug'at o'rganish$"), start_vocab),
                MessageHandler(filters.Regex("^📊 Mening natijalarim$"), show_stats),
                MessageHandler(filters.Regex("^ℹ️ Yordam$"), show_help),
            ],
            LANG_SELECT: [
                CallbackQueryHandler(lang_chosen_test,  pattern="^lang_"),
            ],
            TEST_RUNNING: [
                CallbackQueryHandler(test_answer, pattern="^ans_"),
            ],
            VOCAB_MENU: [
                CallbackQueryHandler(flash_start,        pattern="^flash_start$"),
                CallbackQueryHandler(quiz_start,         pattern="^quiz_start$"),
                CallbackQueryHandler(show_progress_cb,   pattern="^vocab_progress$"),
            ],
            VOCAB_FLASH: [
                CallbackQueryHandler(flash_reveal,       pattern="^flash_reveal$"),
                CallbackQueryHandler(flash_know,         pattern="^flash_know$"),
                CallbackQueryHandler(flash_dontknow,     pattern="^flash_dontknow$"),
                CallbackQueryHandler(flash_restart,      pattern="^flash_restart$"),
                CallbackQueryHandler(vocab_menu_back,    pattern="^vocab_menu$"),
                CallbackQueryHandler(quiz_start,         pattern="^quiz_start$"),
            ],
            VOCAB_QUIZ: [
                CallbackQueryHandler(quiz_answer,        pattern="^qans_"),
                CallbackQueryHandler(quiz_restart,       pattern="^quiz_restart$"),
                CallbackQueryHandler(flash_start,        pattern="^flash_start$"),
                CallbackQueryHandler(vocab_menu_back,    pattern="^vocab_menu$"),
            ],
        },
        fallbacks=[
            CommandHandler("start", cmd_start),
            MessageHandler(filters.TEXT, fallback),
        ],
        per_user=True,
        per_chat=True,
    )

    # lang select for vocab (separate entry)
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(lang_chosen_vocab, pattern="^lang_"))

    print("🤖 Jony Learning Bot ishga tushdi...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

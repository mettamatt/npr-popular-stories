#!/usr/bin/env python
from bs4 import BeautifulSoup
from subprocess import call
from email import utils

import requests, sqlite3, os.path, datetime, eyed3, time

NPR_URL = "http://www.npr.org/series/191676894/most-popular"
AUDIO_STORIES_PATH = '../public_html/npr/stories/'
PODCAST_PATH = '../public_html/npr/podcasts/'
MP3_GAP = '../public_html/npr/2sec.mp3'

# Download a file, but strip off any ? variable and don't overwrite existing files.
def download_file(url):
    local_filename = AUDIO_STORIES_PATH + url.split('/')[-1].split('?')[0]
    if not os.path.isfile(local_filename):
        r = requests.get(url, stream=True)
        with open(local_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:  # filter out keep-alive new chunks
                    f.write(chunk)
                    f.flush()
    return local_filename

db = sqlite3.connect('npr-popular-podcast.db')
c = db.cursor()

#
# STEP 1 - Scrape the website and store the articles.
#
def article_scrape(url):
    """
    Scrape the articles from NPR and save them to the db. Returns number of new articles added.
    :rtype : integer
    """
    soup = BeautifulSoup(requests.get(NPR_URL).text)
    i = 0
    ftr = [60,1] # to convert human-friendly minute into integer seconds.
    for article in soup.find_all("article"):
        if article.li and article.find("a", title="Download"):
            program = article.h2.find("a").contents[0]
            aurl = article.h1.find("a").get("href")
            title = article.h1.find("a").contents[0]
            date = article.time["datetime"]
            file_url = article.find("a", title="Download").get("href")
            duration = article.find('b', 'time-total').contents[0]
            # Convert duration to seconds.
            duration = sum([a*b for a,b in zip(ftr, map(int,duration.split(':')))])
                        
            # Grab the short url. Sadly, this means an additional web request for each article.
            soup2 = BeautifulSoup(requests.get(aurl).text)
            input = soup2.find_all('input', {'type': 'hidden'})
            if input[1]['value']:
                aurl = input[1]['value']

            c.execute('INSERT OR IGNORE INTO article (file_url, title, url, date, program, duration) VALUES (?, ?, ?, ?, ?, ?)',
                      (file_url, title.encode('ascii', 'xmlcharrefreplace'), aurl, date,
                       program.encode('ascii', 'xmlcharrefreplace'), duration))
            i = c.rowcount
            db.commit()

    if i == 1:
        print 'Found 1 new article from NPR.'
    elif i > 1:
        print 'Found ' + str(i) + ' new articles from NPR.'

    return i;

article_scrape(NPR_URL)

#
# Step 2 - Download the audio files & update the db
#
c.execute('SELECT id, file_url FROM article WHERE local_file IS NULL')
rows = c.fetchall()
for row in rows:
    local_file = download_file(row[1])
    c.execute('UPDATE article SET local_file = ? WHERE id = ?', (local_file, row[0]))
    db.commit()

#
# Step 3 - Join audio stories together by day.
# Find the podcasts that need to be created based on the date of the articles.
# Also, add 2 seconds of silence between the clips and add proper ID3 tags.
#

def podcast_generate(date):
    """Generate a new podcast file based on a date, assuming articles exist for that day in the article db table,
        and save it to the database.
    """
    c.execute('SELECT id, title, url, program, local_file, duration FROM article WHERE date = ?', (date, ))
    rows = c.fetchall()
    id, title, url, program, local_file, sduration = ([] for i in range(6))
    for row in rows:
        id.append(row[0])
        title.append(row[1])
        url.append(row[2])
        program.append(row[3])
        local_file.append(row[4])
        local_file.append(MP3_GAP)  # Add a silent clip.
        sduration.append(row[5])

    podcast_fname = '{0}_npr_popular.mp3'.format(str(date))
    podcast_file = PODCAST_PATH + podcast_fname
    if not (os.path.isfile(podcast_file) and local_file):
        with open(podcast_file, "w") as outfile:
            call(['cat'] + local_file, stdout=outfile)  # "Cat" the files via a shell cmd
        audiofile = eyed3.load(podcast_file)
        audiofile.tag.artist = u"NPR"
        audiofile.tag.release_date = str(date)
        audiofile.tag.genre = 101
        audiofile.tag.title = u"NPR Populer Stories for " + str(date)
        audiofile.tag.save()
        print 'Podcast {0} has been generated.'.format(str(date))

    # Now write the new podcast to the db.
    c.execute('SELECT COUNT(pid) FROM podcast WHERE pub_date = ?', (date, ))
    row = c.fetchone();
    if row[0] > 0:
        print 'A podcast for {0} already exists in the db.'.format(str(date))
        pass  # Podcast already exists.
    else:
        human_date = date.strftime("%a, %b %-d")
        pub_date = utils.formatdate(time.mktime(date.timetuple()))  # RFC2822 Date
        ptitle = human_date + ' Most Popular Stories'
        description = ""
        dur = 0
        for index, item in enumerate(title):
            if index > 0:
                dur = dur + sduration[index-1] + 2
            m, s = divmod(dur, 60)
            hdur = "%d:%02d" % (m, s)
            description += str(index + 1) +". "+ item +"("+ hdur +") - "+ url[index] +"\n"
        length = os.path.getsize(podcast_file)
        duration = eyed3.load(podcast_file).info.time_secs
        c.execute(
            'INSERT OR IGNORE INTO podcast (title, description, url, date, pub_date, length, type, duration) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (ptitle, description.encode('ascii', 'xmlcharrefreplace'), podcast_fname, date, pub_date, length,
             'audio/mpeg', duration))
        db.commit()
        print "Podcast {0} has been saved.".format(str(date))

    return podcast_fname

# Retrieve a list of dates we need to generate podcasts for.
c.execute('SELECT article.date '
          'FROM article LEFT JOIN podcast ON article.date = podcast.date '
          'WHERE podcast.date IS NULL GROUP BY article.date')
rows = c.fetchall()
today = datetime.date.today()
for row in rows:
    # Today has not ended so we don't have all the stories.
    if not today == row[0]:
        date = datetime.datetime.strptime(row[0], "%Y-%m-%d").date()
        podcast_generate(date)


#
# Step 5 - Generate the RSS feed
#
def rss_generate():
    """
    Build and return the rss xml.
    :rtype : String
    """
    c.execute('SELECT * FROM podcast ORDER BY date desc')
    rows = c.fetchall()
    item_rss = []
    for row in rows:
        title = row[1]
        description = row[2].encode('utf-8')
        url = row[3]
        pubDate = row[5]
        length = row[6]
        duration = row[8]
        item = """
        <item>
            <title>{title}</title>
            <itunes:author>{author}</itunes:author>
            <description>{description}</description>
            <enclosure url="http://mettamatt.com/npr/podcasts/{mp3}" length="{length}" type="audio/mpeg"/>
            <guid>{guid}</guid>
            <pubDate>{pubDate}</pubDate>
            <itunes:duration>{duration}</itunes:duration>
        </item>
    """.format(
            title=title,
            author="NPR",
            description=description,
            mp3=url,
            length=length,
            guid=url,
            pubDate=pubDate,
            duration=duration
        )
        item_rss.append(item)

    rss = """<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" version="2.0">
    <channel>
        <title>{title}</title>
        <link>{link}</link>
        <description>{description}</description>
        <language>en-us</language>
        <itunes:image href="http://cloudfront.assets.stitcher.com/feedimagesplain328/22491.jpg"/>
        <itunes:category text="News &amp; Politics" />
        {items}
    </channel>
</rss>
    """.format(
        title='NPR: Most Popular Stories Podcast',
        link=NPR_URL,
        description='The most popular stories, delivered daily',
        items="\n".join(item_rss)
    )

    return rss

rss_file = '../public_html/npr/podcast.xml'
fo = open(rss_file, "w+")
fo.write(rss_generate())
fo.close()
db.close()

# NPR Popular Stories Podcast Feed

NPR used to publish a "[most emailed stories](http://www.npr.org/podcasts/500000/most-e-mailed-stories)" podcast in iTunes, however in January 2015 the feed stopped.

This script cobbles together similar collection of stories. Rather than the most emailed stories, it uses the [NPR Popular stories](http://www.npr.org/series/191676894/most-popular) page view. The script uses [BeautifulSoup](http://www.crummy.com/software/BeautifulSoup/) to import the page view and save audio stories and their related metadata in a sqlite database. It then downloads the audio file for each story and joins them together into a single audio file of the most popular stories for each day. 

Finally, the script exports a RSS feed called podcast.xml to consume. 

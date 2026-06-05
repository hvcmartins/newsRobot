"""
Seed the database with catalog sources and two demo tenants.
Run: python -m app.seed
"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.exc import IntegrityError
from app.database import create_tables, SessionLocal
from app.models import CatalogSource, Tenant, Source, CatalogSourceType, SourceType

CATALOG = [
    # Technology
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/", "type": "rss", "category": "Technology", "description": "Startup and tech industry news", "language": "en", "country": "US"},
    {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml", "type": "rss", "category": "Technology", "description": "Technology, science, art and culture", "language": "en", "country": "US"},
    {"name": "Wired", "url": "https://www.wired.com/feed/rss", "type": "rss", "category": "Technology", "description": "Tech culture and future of innovation", "language": "en", "country": "US"},
    {"name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/index", "type": "rss", "category": "Technology", "description": "In-depth technology news and analysis", "language": "en", "country": "US"},
    {"name": "MIT Technology Review", "url": "https://www.technologyreview.com/feed/", "type": "rss", "category": "Technology", "description": "MIT's technology journalism publication", "language": "en", "country": "US"},
    {"name": "Hacker News", "url": "https://news.ycombinator.com/rss", "type": "rss", "category": "Technology", "description": "Y Combinator community tech news", "language": "en", "country": "US"},
    {"name": "VentureBeat", "url": "https://venturebeat.com/feed/", "type": "rss", "category": "Technology", "description": "Tech and AI news for enterprise", "language": "en", "country": "US"},

    # Finance
    {"name": "Reuters Business", "url": "https://feeds.reuters.com/reuters/businessNews", "type": "rss", "category": "Finance", "description": "Global business and financial news", "language": "en", "country": "GB"},
    {"name": "Bloomberg Markets", "url": "https://feeds.bloomberg.com/markets/news.rss", "type": "rss", "category": "Finance", "description": "Financial markets and economics", "language": "en", "country": "US"},
    {"name": "CNBC Finance", "url": "https://www.cnbc.com/id/10000664/device/rss/rss.html", "type": "rss", "category": "Finance", "description": "CNBC financial news feed", "language": "en", "country": "US"},
    {"name": "MarketWatch", "url": "https://feeds.marketwatch.com/marketwatch/topstories/", "type": "rss", "category": "Finance", "description": "Stock market and business news", "language": "en", "country": "US"},
    {"name": "Seeking Alpha", "url": "https://seekingalpha.com/feed.xml", "type": "rss", "category": "Finance", "description": "Investment analysis and financial news", "language": "en", "country": "US"},

    # Business
    {"name": "Harvard Business Review", "url": "https://hbr.org/rss.xml", "type": "rss", "category": "Business", "description": "Management and leadership insights", "language": "en", "country": "US"},
    {"name": "Fast Company", "url": "https://www.fastcompany.com/rss", "type": "rss", "category": "Business", "description": "Innovation in business and design", "language": "en", "country": "US"},
    {"name": "Inc. Magazine", "url": "https://www.inc.com/rss", "type": "rss", "category": "Business", "description": "Entrepreneurship and small business", "language": "en", "country": "US"},
    {"name": "Forbes", "url": "https://www.forbes.com/real-time/feed2/", "type": "rss", "category": "Business", "description": "Business and wealth news", "language": "en", "country": "US"},

    # World News
    {"name": "BBC News", "url": "http://feeds.bbci.co.uk/news/rss.xml", "type": "rss", "category": "World News", "description": "BBC global news coverage", "language": "en", "country": "GB"},
    {"name": "Reuters Top News", "url": "https://feeds.reuters.com/reuters/topNews", "type": "rss", "category": "World News", "description": "Reuters international news", "language": "en", "country": "GB"},
    {"name": "AP News", "url": "https://rsshub.app/apnews/topics/apf-topnews", "type": "rss", "category": "World News", "description": "Associated Press top stories", "language": "en", "country": "US"},
    {"name": "Al Jazeera English", "url": "https://www.aljazeera.com/xml/rss/all.xml", "type": "rss", "category": "World News", "description": "Global news with a focus on developing world", "language": "en", "country": "QA"},
    {"name": "The Guardian World", "url": "https://www.theguardian.com/world/rss", "type": "rss", "category": "World News", "description": "Guardian international news", "language": "en", "country": "GB"},

    # Science
    {"name": "Nature News", "url": "https://www.nature.com/nature.rss", "type": "rss", "category": "Science", "description": "Leading science journal news", "language": "en", "country": "GB"},
    {"name": "Science Daily", "url": "https://www.sciencedaily.com/rss/all.xml", "type": "rss", "category": "Science", "description": "Latest research news across all sciences", "language": "en", "country": "US"},
    {"name": "New Scientist", "url": "https://www.newscientist.com/feed/home/", "type": "rss", "category": "Science", "description": "Science and technology weekly", "language": "en", "country": "GB"},
    {"name": "NASA News", "url": "https://www.nasa.gov/rss/dyn/breaking_news.rss", "type": "rss", "category": "Science", "description": "NASA announcements and discoveries", "language": "en", "country": "US"},
    {"name": "Phys.org", "url": "https://phys.org/rss-feed/", "type": "rss", "category": "Science", "description": "Physics and technology research news", "language": "en", "country": "US"},

    # Health
    {"name": "WHO News", "url": "https://www.who.int/rss-feeds/news-english.xml", "type": "rss", "category": "Health", "description": "World Health Organization updates", "language": "en", "country": "CH"},
    {"name": "WebMD Health News", "url": "https://rssfeeds.webmd.com/rss/rss.aspx?RSSSource=RSS_PUBLIC", "type": "rss", "category": "Health", "description": "Medical and health news", "language": "en", "country": "US"},
    {"name": "Healthline", "url": "https://www.healthline.com/rss/health-news", "type": "rss", "category": "Health", "description": "Evidence-based health information", "language": "en", "country": "US"},

    # Politics
    {"name": "Politico", "url": "https://www.politico.com/rss/politicopicks.xml", "type": "rss", "category": "Politics", "description": "US and European political news", "language": "en", "country": "US"},
    {"name": "The Hill", "url": "https://thehill.com/rss/syndication/all-news", "type": "rss", "category": "Politics", "description": "US political and policy news", "language": "en", "country": "US"},
    {"name": "NPR Politics", "url": "https://feeds.npr.org/1014/rss.xml", "type": "rss", "category": "Politics", "description": "NPR political coverage", "language": "en", "country": "US"},

    # Sports
    {"name": "ESPN", "url": "https://www.espn.com/espn/rss/news", "type": "rss", "category": "Sports", "description": "Sports news and analysis", "language": "en", "country": "US"},
    {"name": "BBC Sport", "url": "http://feeds.bbci.co.uk/sport/rss.xml", "type": "rss", "category": "Sports", "description": "BBC sports coverage", "language": "en", "country": "GB"},
    {"name": "Sky Sports News", "url": "https://www.skysports.com/rss/12040", "type": "rss", "category": "Sports", "description": "Latest sports news from Sky", "language": "en", "country": "GB"},

    # Environment
    {"name": "The Guardian Environment", "url": "https://www.theguardian.com/environment/rss", "type": "rss", "category": "Environment", "description": "Climate and environmental news", "language": "en", "country": "GB"},
    {"name": "Yale Environment 360", "url": "https://e360.yale.edu/feed", "type": "rss", "category": "Environment", "description": "Environment, energy, and climate analysis", "language": "en", "country": "US"},
    {"name": "Carbon Brief", "url": "https://www.carbonbrief.org/feed", "type": "rss", "category": "Environment", "description": "Clear, data-driven climate science reporting", "language": "en", "country": "GB"},

    # AI / Machine Learning
    {"name": "Google AI Blog", "url": "https://blog.research.google/feeds/posts/default", "type": "rss", "category": "Technology", "description": "Google research and AI updates", "language": "en", "country": "US"},
    {"name": "OpenAI Blog", "url": "https://openai.com/blog/rss.xml", "type": "rss", "category": "Technology", "description": "OpenAI research and product announcements", "language": "en", "country": "US"},
    {"name": "Towards Data Science", "url": "https://towardsdatascience.com/feed", "type": "rss", "category": "Technology", "description": "Data science and ML tutorials and news", "language": "en", "country": "US"},

    # Cybersecurity
    {"name": "Krebs on Security", "url": "https://krebsonsecurity.com/feed/", "type": "rss", "category": "Technology", "description": "Investigative cybersecurity journalism", "language": "en", "country": "US"},
    {"name": "The Hacker News", "url": "https://feeds.feedburner.com/TheHackersNews", "type": "rss", "category": "Technology", "description": "Cybersecurity news and analysis", "language": "en", "country": "US"},
    {"name": "Dark Reading", "url": "https://www.darkreading.com/rss.xml", "type": "rss", "category": "Technology", "description": "Enterprise security news", "language": "en", "country": "US"},

    # Crypto / Blockchain
    {"name": "CoinDesk", "url": "https://www.coindesk.com/arc/outboundfeeds/rss/", "type": "rss", "category": "Finance", "description": "Cryptocurrency and blockchain news", "language": "en", "country": "US"},
    {"name": "Cointelegraph", "url": "https://cointelegraph.com/rss", "type": "rss", "category": "Finance", "description": "Bitcoin, Ethereum and crypto news", "language": "en", "country": "US"},

    # General
    {"name": "The Economist", "url": "https://www.economist.com/latest/rss.xml", "type": "rss", "category": "Business", "description": "World news, politics, economics and culture", "language": "en", "country": "GB"},
]

DEMO_TENANTS = [
    {
        "name": "Acme Corp",
        "slug": "acme",
        "primary_color": "#e63946",
        "topic_profile": "Acme Corp is a technology company focused on cloud software and developer tools. We track news about software development, cloud computing, developer ecosystems, startup funding, and major tech acquisitions.",
        "global_keywords": json.dumps(["cloud", "developer", "API", "SaaS", "startup"]),
        "schedule_cron": "0 * * * *",
        "source_categories": ["Technology", "Business"],
    },
    {
        "name": "GreenFuture Investments",
        "slug": "greenfuture",
        "primary_color": "#2d6a4f",
        "topic_profile": "GreenFuture is a renewable energy investment fund. We monitor news about solar, wind, and battery storage markets, green energy policy changes, ESG investing trends, and climate regulations in Europe and North America.",
        "global_keywords": json.dumps(["solar", "wind", "renewable", "ESG", "climate", "battery"]),
        "schedule_cron": "0 */2 * * *",
        "source_categories": ["Environment", "Finance", "Business"],
    },
]


def seed():
    create_tables()
    db = SessionLocal()
    try:
        # Seed catalog
        existing_urls = {cs.url for cs in db.query(CatalogSource).all()}
        added = 0
        for entry in CATALOG:
            if entry["url"] not in existing_urls:
                cs = CatalogSource(
                    name=entry["name"],
                    url=entry["url"],
                    type=CatalogSourceType(entry.get("type", "rss")),
                    category=entry["category"],
                    description=entry.get("description"),
                    language=entry.get("language", "en"),
                    country=entry.get("country"),
                    is_verified=True,
                )
                db.add(cs)
                try:
                    db.commit()
                    added += 1
                except IntegrityError:
                    db.rollback()
        print(f"Catalog: added {added} sources ({len(CATALOG) - added} already present)")

        # Seed demo tenants
        for tdata in DEMO_TENANTS:
            if db.query(Tenant).filter_by(slug=tdata["slug"]).first():
                print(f"Tenant '{tdata['slug']}' already exists, skipping")
                continue

            tenant = Tenant(
                name=tdata["name"],
                slug=tdata["slug"],
                primary_color=tdata["primary_color"],
                topic_profile=tdata["topic_profile"],
                global_keywords=tdata["global_keywords"],
                schedule_cron=tdata["schedule_cron"],
            )
            db.add(tenant)
            db.flush()

            # Add 3 sources from catalog for each demo category
            for cat in tdata["source_categories"]:
                catalog_sources = (db.query(CatalogSource)
                                   .filter_by(category=cat)
                                   .limit(3)
                                   .all())
                for cs in catalog_sources:
                    source = Source(
                        tenant_id=tenant.id,
                        catalog_source_id=cs.id,
                        name=cs.name,
                        url=cs.url,
                        type=SourceType(cs.type.value),
                        is_active=True,
                    )
                    db.add(source)

            db.commit()
            print(f"Tenant '{tdata['name']}' created with sources")

    finally:
        db.close()


if __name__ == "__main__":
    seed()

# API Configuration Guide for FinBot v2.0

This document lists all external API keys required for full functionality.

## ✅ MANDATORY APIs (Core Features)

None - All core features work without API keys.

## 🔌 OPTIONAL APIs (Enhanced Features)

### 1. Real-time Sentiment Analysis (Priority 2)

#### NewsAPI (Recommended)
- **Purpose**: Fetch financial news headlines
- **Get key**: https://newsapi.org/register
- **Free tier**: 100 requests/day, 30-day history
- **Env variable**: `NEWSAPI_KEY`
- **Usage**: `RealtimeSentimentPipeline._fetch_news()`

```bash
export NEWSAPI_KEY="your_newsapi_key_here"
```

#### Alpha Vantage News Sentiment (Recommended)
- **Purpose**: Pre-scored financial news sentiment
- **Get key**: https://www.alphavantage.co/support/#api-key
- **Free tier**: 500 requests/day
- **Env variable**: `ALPHA_VANTAGE_KEY`
- **Usage**: `RealtimeSentimentPipeline._fetch_alpha_vantage()`

```bash
export ALPHA_VANTAGE_KEY="your_alpha_vantage_key"
```

#### Twitter API v2 (Optional)
- **Purpose**: Real-time social sentiment from Twitter
- **Get key**: https://developer.twitter.com/en/portal/dashboard
- **Free tier**: Essential (500k tweets/month)
- **Env variable**: `TWITTER_BEARER_TOKEN`
- **Usage**: `RealtimeSentimentPipeline._fetch_twitter()`
- **Note**: Requires tweepy>=4.14.0 (add to requirements.txt if needed)

```bash
export TWITTER_BEARER_TOKEN="your_twitter_bearer_token"
```

#### Reddit API (Optional)
- **Purpose**: Sentiment from r/wallstreetbets, r/stocks
- **Get credentials**: https://www.reddit.com/prefs/apps
- **Free tier**: 60 requests/minute
- **Env variables**: `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT`
- **Usage**: `RealtimeSentimentPipeline._fetch_reddit()`
- **Note**: Requires praw (add to requirements.txt if needed)

```bash
export REDDIT_CLIENT_ID="your_reddit_client_id"
export REDDIT_CLIENT_SECRET="your_reddit_client_secret"
export REDDIT_USER_AGENT="FinBot/2.0"
```

## 📋 Current Status

### Active APIs (in .env)
Check your `.env` file for existing keys:

```bash
cd /workspaces/finbot
grep -E "NEWSAPI|ALPHA_VANTAGE|TWITTER|REDDIT" .env
```

### Recommended Setup (Minimal)

For **real-time sentiment** with minimal cost:

1. **NewsAPI** (free, 100 req/day) → Primary news source
2. **Alpha Vantage** (free, 500 req/day) → Backup + pre-scored sentiment

This gives you ~600 sentiment queries/day for free.

### Full Setup (Maximum Coverage)

Add all 4 APIs for comprehensive multi-source sentiment:
- NewsAPI (general news)
- Alpha Vantage (financial news + sentiment scores)
- Twitter (real-time social sentiment)
- Reddit (retail investor sentiment)

## 🔧 Setup Instructions

### Step 1: Create .env file

```bash
cd /workspaces/finbot
cp .env.example .env  # If exists
nano .env
```

### Step 2: Add API keys

```bash
# Sentiment APIs (Optional - for RealtimeSentimentPipeline)
NEWSAPI_KEY=your_newsapi_key_here
ALPHA_VANTAGE_KEY=your_alpha_vantage_key
# TWITTER_BEARER_TOKEN=your_twitter_token  # Uncomment if using Twitter
# REDDIT_CLIENT_ID=your_reddit_client_id  # Uncomment if using Reddit
# REDDIT_CLIENT_SECRET=your_reddit_secret
# REDDIT_USER_AGENT=FinBot/2.0
```

### Step 3: Install optional dependencies (if using Twitter/Reddit)

```bash
# For Twitter
pip install tweepy>=4.14.0

# For Reddit
pip install praw>=7.7.0
```

Or add to `requirements.txt`:

```txt
# Optional: Real-time Sentiment (Priority 2)
# tweepy>=4.14.0  # Twitter API v2
# praw>=7.7.0     # Reddit API
```

### Step 4: Verify setup

```python
from financial_analyzer.sentiment import RealtimeSentimentPipeline

# Initialize pipeline (will warn if keys missing)
pipeline = RealtimeSentimentPipeline(
    use_newsapi=True,
    use_alpha_vantage=True,
    use_twitter=False,  # Set True if you have token
    use_reddit=False,   # Set True if you have credentials
)

# Test sentiment fetch
result = pipeline.get_sentiment('AAPL', hours_back=24)
print(f"Sentiment: {result['sentiment_score']:.2f}")
print(f"Sources used: {result['sources']}")
```

## 🚨 Troubleshooting

### "No sentiment sources available"
→ All API keys are missing/invalid. Add at least one key (NewsAPI or Alpha Vantage recommended).

### "Rate limit exceeded"
→ Free tier limits reached. Wait for reset or upgrade plan.

### "Module tweepy not found"
→ Twitter integration used without installing tweepy: `pip install tweepy`

### "Module praw not found"
→ Reddit integration used without installing praw: `pip install praw`

## 📊 Cost Comparison

| API | Free Tier | Paid Tier | Use Case |
|-----|-----------|-----------|----------|
| NewsAPI | 100 req/day | $449/mo (unlimited) | General news |
| Alpha Vantage | 500 req/day | $50/mo (1200/day) | Financial news |
| Twitter | 500k tweets/mo | $100/mo+ | Social sentiment |
| Reddit | 60 req/min | N/A (free only) | Retail sentiment |

**Recommendation**: Start with free tiers (NewsAPI + Alpha Vantage). Upgrade only if you need >600 sentiment queries/day.

## 🎯 Priority Recommendation

**For FinBot v2.0 (current state):**

1. ✅ **Get NewsAPI key** (5 min, free) → Primary sentiment source
2. ✅ **Get Alpha Vantage key** (5 min, free) → Backup + pre-scored data
3. ⏸️ **Skip Twitter/Reddit** for now → Only needed for social sentiment focus

This minimal setup enables:
- Real-time multi-source sentiment
- ~600 free queries/day
- No credit card required
- 10 minutes total setup time

---

**Last updated**: 2025-11-24
**Module**: `RealtimeSentimentPipeline` (Priority 2)
**Status**: Fully implemented, awaiting API keys for testing

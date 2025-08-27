from crewai import Agent, Task, Crew, Process
from crewai_tools import MCPServerAdapter
from mcp import StdioServerParameters
from crewai.llm import LLM
import os
import json
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from textblob import TextBlob

load_dotenv()


llm = LLM(
    model="nebius/Qwen/Qwen3-235B-A22B",
    api_key=os.getenv("NEBIUS_API_KEY")
)

server_params = StdioServerParameters(
    command="npx",
    args=["@brightdata/mcp"],
    env={
        "API_TOKEN": os.getenv("BRIGHT_DATA_API_TOKEN"),
        "WEB_UNLOCKER_ZONE": os.getenv("WEB_UNLOCKER_ZONE"),
        "BROWSER_ZONE": os.getenv("BROWSER_ZONE"),
    },
)

def build_review_scraper_agent(mcp_tools):
    return Agent(
        role="Review Data Collector",
        goal=(
            "Extract customer reviews from multiple platforms and return clean, "
            "structured JSON data with review text, ratings, dates, and platform source."
        ),
        backstory=(
            "Expert in web scraping with deep knowledge of review platform structures. "
            "Skilled at bypassing anti-bot measures and extracting complete review datasets "
            "from Amazon, Yelp, Google Reviews, and other platforms."
        ),
        tools=mcp_tools,
        llm=llm,
        max_iter=3,
        verbose=True,
    )

def build_sentiment_analyzer_agent():
    return Agent(
        role="Sentiment Analysis Specialist",
        goal=(
            "Analyze review sentiment across three key aspects: Support Quality, "
            "Pricing Satisfaction, and Ease of Use. Provide numerical scores and "
            "detailed reasoning for each category."
        ),
        backstory=(
            "Data scientist specializing in natural language processing and customer "
            "sentiment analysis. Expert at identifying emotional indicators, context clues, "
            "and aspect-specific feedback patterns in customer reviews."
        ),
        llm=llm,
        max_iter=2,
        verbose=True,
    )

def build_insights_generator_agent():
    return Agent(
        role="Business Intelligence Analyst",
        goal=(
            "Transform sentiment analysis results into actionable business insights. "
            "Identify trends, highlight critical issues, and provide specific "
            "recommendations for improvement."
        ),
        backstory=(
            "Strategic analyst with expertise in customer experience optimization. "
            "Skilled at translating customer feedback data into concrete business "
            "actions and priority frameworks."
        ),
        llm=llm,
        max_iter=2,
        verbose=True,
    )

def build_scraping_task(agent, product_urls):
    return Task(
        description=f"Scrape reviews from these product pages: {product_urls}",
        expected_output="""{
            "reviews": [
                {
                    "platform": "amazon",
                    "review_text": "Great product, fast shipping...",
                    "rating": 5,
                    "date": "2024-01-15",
                    "reviewer_name": "John D.",
                    "verified_purchase": true
                }
            ],
            "total_reviews": 150,
            "platforms_scraped": ["amazon", "yelp"]
        }""",
        agent=agent,
    )

def build_sentiment_analysis_task(agent):
    return Task(
        description="Analyze sentiment for Support, Pricing, and Ease of Use aspects",
        expected_output="""{
            "aspect_analysis": {
                "support_quality": {
                    "score": 4.2,
                    "sentiment": "positive",
                    "key_themes": ["responsive", "helpful", "knowledgeable"],
                    "review_count": 45
                },
                "pricing_satisfaction": {
                    "score": 3.1,
                    "sentiment": "mixed",
                    "key_themes": ["expensive", "value", "competitive"],
                    "review_count": 67
                },
                "ease_of_use": {
                    "score": 4.7,
                    "sentiment": "very positive",
                    "key_themes": ["intuitive", "simple", "user-friendly"],
                    "review_count": 89
                }
            }
        }""",
        agent=agent,
    )

def build_insights_task(agent):
    return Task(
        description="Generate actionable business insights from sentiment analysis",
        expected_output="""{
            "executive_summary": "Overall customer satisfaction is strong...",
            "priority_actions": [
                "Address pricing concerns through value communication",
                "Maintain excellent ease of use standards"
            ],
            "risk_areas": ["Price sensitivity among new customers"],
            "strengths": ["Intuitive user experience", "Quality support team"],
            "recommended_focus": "Pricing strategy optimization"
        }""",
        agent=agent,
    )

def analyze_aspect_sentiment(reviews, aspect_keywords):
    """Analyze sentiment for specific aspects mentioned in reviews."""
    aspect_reviews = []
    
    for review in reviews:
        text = review.get('review_text', '').lower()
        if any(keyword in text for keyword in aspect_keywords):
            blob = TextBlob(review['review_text'])
            sentiment_score = blob.sentiment.polarity
            
            aspect_reviews.append({
                'text': review['review_text'],
                'sentiment_score': sentiment_score,
                'rating': review.get('rating', 0),
                'platform': review.get('platform', '')
            })
    
    return aspect_reviews

def categorize_by_aspects(reviews):
    """Categorize reviews into Support, Pricing, and Ease of Use topics."""
    
    support_keywords = ['support', 'help', 'service', 'customer', 'response', 'assistance']
    pricing_keywords = ['price', 'cost', 'expensive', 'cheap', 'value', 'money', 'affordable']
    usability_keywords = ['easy', 'difficult', 'intuitive', 'complicated', 'user-friendly', 'interface']
    
    categorized = {
        'support': analyze_aspect_sentiment(reviews, support_keywords),
        'pricing': analyze_aspect_sentiment(reviews, pricing_keywords),
        'ease_of_use': analyze_aspect_sentiment(reviews, usability_keywords)
    }
    
    return categorized

def calculate_aspect_scores(categorized_reviews):
    """Calculate numerical scores for each aspect category."""
    
    scores = {}
    
    for aspect, reviews in categorized_reviews.items():
        if not reviews:
            scores[aspect] = {'score': 0, 'count': 0, 'sentiment': 'neutral'}
            continue
            
        # Calculate average sentiment score
        sentiment_scores = [r['sentiment_score'] for r in reviews]
        avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
        
        # Convert to 1-5 scale
        normalized_score = ((avg_sentiment + 1) / 2) * 5
        
        # Determine sentiment category
        if avg_sentiment > 0.3:
            sentiment_category = 'positive'
        elif avg_sentiment < -0.3:
            sentiment_category = 'negative'
        else:
            sentiment_category = 'neutral'
            
        scores[aspect] = {
            'score': round(normalized_score, 1),
            'count': len(reviews),
            'sentiment': sentiment_category,
            'raw_sentiment': round(avg_sentiment, 2)
        }
    
    return scores

def analyze_reviews(product_urls):
    """Main function to orchestrate the review intelligence workflow."""
    
    with MCPServerAdapter(server_params) as mcp_tools:
        # Create agents
        scraper_agent = build_review_scraper_agent(mcp_tools)
        sentiment_agent = build_sentiment_analyzer_agent()
        insights_agent = build_insights_generator_agent()
        
        # Create tasks
        scraping_task = build_scraping_task(scraper_agent, product_urls)
        sentiment_task = build_sentiment_analysis_task(sentiment_agent)
        insights_task = build_insights_task(insights_agent)
        
        # Assemble crew
        crew = Crew(
            agents=[scraper_agent, sentiment_agent, insights_agent],
            tasks=[scraping_task, sentiment_task, insights_task],
            process=Process.sequential,
            verbose=True
        )
        
        return crew.kickoff()

if __name__ == "__main__":
    product_urls = [
        "https://www.trustpilot.com/review/www.dugood.org",
        "https://www.trustpilot.com/review/www.moneyadvisor.co.uk"
    ]
    
    try:
        result = analyze_reviews(product_urls)
        print("Review Intelligence Analysis Complete!")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Analysis failed: {str(e)}")		


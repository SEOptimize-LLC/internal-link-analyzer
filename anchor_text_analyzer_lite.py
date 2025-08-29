"""
Lightweight Anchor Text Analyzer - No NLTK dependency
Provides basic anchor text analysis for Streamlit Cloud compatibility
"""

import re
from typing import List, Dict
from collections import defaultdict, Counter

class AnchorTextAnalyzerLite:
    """Lightweight version of anchor text analyzer without NLTK dependency"""

    def __init__(self):
        # Basic stop words without NLTK
        self.stop_words = {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
            'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
            'to', 'was', 'were', 'will', 'with', 'but', 'or', 'not', 'this',
            'these', 'those', 'i', 'you', 'we', 'they', 'he', 'she', 'it',
            'me', 'us', 'them', 'my', 'your', 'our', 'their', 'his', 'her',
            'its', 'what', 'which', 'who', 'when', 'where', 'why', 'how'
        }

    def analyze_uniqueness(self, links: List[Dict]) -> Dict[str, List[Dict]]:
        """Analyze anchor text uniqueness across the site"""
        issues = defaultdict(list)

        # Group links by anchor text (case-insensitive)
        anchor_groups = defaultdict(list)

        for link in links:
            anchor_key = link['anchor'].strip().lower()
            if anchor_key:
                anchor_groups[anchor_key].append(link)

        # Find non-unique anchor texts
        for anchor_text, link_list in anchor_groups.items():
            if len(link_list) > 1:
                # Check if they point to different destinations
                destinations = set(link['url'] for link in link_list)
                if len(destinations) > 1:
                    issues['non_unique_anchors'].append({
                        'anchor_text': anchor_text,
                        'links': link_list,
                        'unique_destinations': len(destinations),
                        'severity': 'high' if len(destinations) > 3 else 'medium'
                    })

        return dict(issues)

    def score_anchor_text(self, anchor_text: str, context: Dict = None) -> Dict[str, float]:
        """Score anchor text on multiple optimization dimensions (simplified)"""
        scores = {}

        # Length Score (1-100)
        length = len(anchor_text)
        if 1 <= length <= 60:
            scores['length'] = 100
        elif length <= 100:
            scores['length'] = 80
        else:
            scores['length'] = max(0, 100 - (length - 100))

        # Basic keyword density (simplified without NLTK)
        words = self._simple_tokenize(anchor_text)
        keywords = [word for word in words if word not in self.stop_words and len(word) > 2]

        if len(words) == 0:
            scores['keyword_density'] = 0
        else:
            density = len(keywords) / len(words)
            if density <= 0.3:
                scores['keyword_density'] = 100
            elif density <= 0.5:
                scores['keyword_density'] = 80
            elif density <= 0.7:
                scores['keyword_density'] = 50
            else:
                scores['keyword_density'] = 20

        # Basic specificity check
        generic_terms = {
            'click here', 'read more', 'learn more', 'here', 'more',
            'continue reading', 'see more', 'view more', 'find out more',
            'download', 'buy now', 'shop now', 'contact us', 'about us'
        }

        if anchor_text.lower().strip() in generic_terms:
            scores['specificity'] = 20
        else:
            scores['specificity'] = 100

        # Overall Score (weighted average)
        weights = {
            'length': 0.4,
            'keyword_density': 0.3,
            'specificity': 0.3
        }

        overall_score = sum(scores[metric] * weights[metric] for metric in weights.keys() if metric in scores)
        scores['overall'] = overall_score

        return scores

    def _simple_tokenize(self, text: str) -> List[str]:
        """Simple tokenization without NLTK"""
        # Remove punctuation and split
        text = re.sub(r'[^\w\s]', '', text)
        return text.lower().split()

    def detect_over_optimization(self, links: List[Dict]) -> List[Dict]:
        """Detect over-optimization patterns (simplified)"""
        issues = []

        # Analyze anchor text distribution
        anchor_texts = [link['anchor'].strip().lower() for link in links if link['anchor'].strip()]

        if not anchor_texts:
            return issues

        # Simple over-optimization check
        short_anchors = sum(1 for anchor in anchor_texts if len(anchor.split()) <= 3)
        total_anchors = len(anchor_texts)
        short_percentage = (short_anchors / total_anchors) * 100

        # Flag potential over-optimization
        if short_percentage > 70:
            issues.append({
                'type': 'over_optimization',
                'severity': 'medium',
                'message': f'High percentage of short anchor texts ({short_percentage:.1f}%)',
                'recommendation': 'Consider using more descriptive anchor text'
            })

        return issues

    def generate_recommendations(self, anchor_text: str, scores: Dict[str, float]) -> List[str]:
        """Generate specific recommendations for anchor text optimization"""
        recommendations = []

        if scores.get('length', 100) < 70:
            if len(anchor_text) > 60:
                recommendations.append("Shorten anchor text to 60 characters or less")
            elif len(anchor_text) < 3:
                recommendations.append("Lengthen anchor text to at least 3 characters")

        if scores.get('keyword_density', 100) < 70:
            recommendations.append("Reduce keyword density - use more natural language")

        if scores.get('specificity', 100) < 70:
            recommendations.append("Replace generic terms with specific, descriptive text")

        if scores.get('overall', 100) < 50:
            recommendations.append("Consider completely rewriting this anchor text")

        return recommendations
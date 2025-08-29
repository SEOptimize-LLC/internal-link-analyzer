import re
import string
from collections import defaultdict, Counter
from typing import List, Dict, Tuple, Set
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

class AnchorTextAnalyzer:
    def __init__(self):
        # Download NLTK data if needed
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt', quiet=True)
        try:
            nltk.data.find('corpora/stopwords')
        except LookupError:
            nltk.download('stopwords', quiet=True)

        self.stop_words = set(stopwords.words('english'))

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
        """Score anchor text on multiple optimization dimensions"""
        scores = {}

        # Length Score (1-100)
        length = len(anchor_text)
        if 1 <= length <= 60:
            scores['length'] = 100
        elif length <= 100:
            scores['length'] = 80
        else:
            scores['length'] = max(0, 100 - (length - 100))

        # Keyword Density Score
        words = self._tokenize_text(anchor_text)
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

        # Natural Language Score
        scores['natural_language'] = self._calculate_natural_language_score(anchor_text)

        # Generic Term Detection
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
            'length': 0.2,
            'keyword_density': 0.3,
            'natural_language': 0.3,
            'specificity': 0.2
        }

        overall_score = sum(scores[metric] * weights[metric] for metric in weights.keys() if metric in scores)
        scores['overall'] = overall_score

        return scores

    def _tokenize_text(self, text: str) -> List[str]:
        """Tokenize text into words"""
        # Remove punctuation and tokenize
        text = text.translate(str.maketrans('', '', string.punctuation))
        return word_tokenize(text.lower())

    def _calculate_natural_language_score(self, text: str) -> float:
        """Calculate how natural the language sounds"""
        if not text or len(text.strip()) == 0:
            return 0

        # Check for keyword stuffing patterns
        words = self._tokenize_text(text)
        if len(words) == 0:
            return 0

        # Count repeated words
        word_counts = Counter(words)
        repeated_words = sum(1 for count in word_counts.values() if count > 1)

        # Penalize excessive repetition
        repetition_penalty = min(100, repeated_words * 20)

        # Check for natural sentence structure
        has_sentence_structure = any(char in text for char in ['.', '!', '?', ','])

        base_score = 100 - repetition_penalty

        if has_sentence_structure:
            base_score += 10

        return max(0, min(100, base_score))

    def detect_over_optimization(self, links: List[Dict]) -> List[Dict]:
        """Detect over-optimization patterns"""
        issues = []

        # Analyze anchor text distribution
        anchor_texts = [link['anchor'].strip().lower() for link in links if link['anchor'].strip()]

        if not anchor_texts:
            return issues

        # Count exact match vs partial match vs branded
        exact_match_count = 0
        branded_count = 0
        generic_count = 0

        for anchor in anchor_texts:
            if len(anchor.split()) <= 3:  # Short anchors often exact match
                exact_match_count += 1
            elif any(term in anchor for term in ['company', 'brand', 'website', 'site']):
                branded_count += 1
            elif anchor in ['click here', 'read more', 'learn more', 'here']:
                generic_count += 1

        total_anchors = len(anchor_texts)
        exact_match_percentage = (exact_match_count / total_anchors) * 100

        # Flag over-optimization
        if exact_match_percentage > 60:
            issues.append({
                'type': 'over_optimization',
                'severity': 'high',
                'message': f'High exact match anchor text usage ({exact_match_percentage:.1f}%)',
                'recommendation': 'Diversify anchor text types and reduce exact match usage below 40%'
            })
        elif exact_match_percentage > 40:
            issues.append({
                'type': 'over_optimization',
                'severity': 'medium',
                'message': f'Moderate exact match anchor text usage ({exact_match_percentage:.1f}%)',
                'recommendation': 'Consider adding more varied anchor text types'
            })

        return issues

    def generate_recommendations(self, anchor_text: str, scores: Dict[str, float]) -> List[str]:
        """Generate specific recommendations for anchor text optimization"""
        recommendations = []

        if scores.get('length', 100) < 70:
            if len(anchor_text) > 60:
                recommendations.append("Shorten anchor text to 60 characters or less for better readability")
            elif len(anchor_text) < 3:
                recommendations.append("Lengthen anchor text to at least 3 characters for better context")

        if scores.get('keyword_density', 100) < 70:
            recommendations.append("Reduce keyword density - use more natural language")

        if scores.get('natural_language', 100) < 70:
            recommendations.append("Make anchor text more conversational and natural-sounding")

        if scores.get('specificity', 100) < 70:
            recommendations.append("Replace generic terms with specific, descriptive text")

        if scores.get('overall', 100) < 50:
            recommendations.append("Consider completely rewriting this anchor text for better optimization")

        return recommendations
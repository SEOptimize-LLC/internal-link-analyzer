from typing import List, Dict, Any
from collections import defaultdict
import pandas as pd

class RecommendationEngine:
    def __init__(self):
        self.priority_levels = {
            'critical': 1,
            'high': 2,
            'medium': 3,
            'low': 4
        }

    def generate_comprehensive_recommendations(self,
                                             duplicate_links: List[Dict],
                                             anchor_issues: Dict[str, List],
                                             optimization_scores: Dict[str, Dict],
                                             site_summary: Dict) -> List[Dict]:
        """Generate prioritized recommendations for the entire site"""

        recommendations = []

        # 1. Duplicate Link Recommendations
        duplicate_recs = self._generate_duplicate_recommendations(duplicate_links)
        recommendations.extend(duplicate_recs)

        # 2. Anchor Text Uniqueness Recommendations
        uniqueness_recs = self._generate_uniqueness_recommendations(anchor_issues)
        recommendations.extend(uniqueness_recs)

        # 3. Optimization Recommendations
        optimization_recs = self._generate_optimization_recommendations(optimization_scores)
        recommendations.extend(optimization_recs)

        # 4. Site-wide Recommendations
        site_recs = self._generate_site_recommendations(site_summary)
        recommendations.extend(site_recs)

        # Sort by priority
        recommendations.sort(key=lambda x: (self.priority_levels.get(x['priority'], 5), x['impact']))

        return recommendations

    def _generate_duplicate_recommendations(self, duplicate_links: List[Dict]) -> List[Dict]:
        """Generate recommendations for duplicate links"""
        recommendations = []

        if not duplicate_links:
            return recommendations

        # Group by target URL
        target_groups = defaultdict(list)
        for link in duplicate_links:
            target_groups[link['target_url']].append(link)

        for target_url, links in target_groups.items():
            if len(links) > 1:
                recommendations.append({
                    'type': 'duplicate_links',
                    'priority': 'high',
                    'impact': 'high',
                    'title': f'Remove duplicate links on {target_url.split("/")[-1] or "homepage"}',
                    'description': f'Found {len(links)} duplicate links pointing to the same destination',
                    'action_items': [
                        'Keep the most contextually relevant link',
                        'Remove or modify the remaining duplicate links',
                        'Ensure each link adds unique value to the page'
                    ],
                    'affected_urls': [link['target_url'] for link in links],
                    'estimated_seo_impact': 'Medium - Prevents link equity dilution'
                })

        return recommendations

    def _generate_uniqueness_recommendations(self, anchor_issues: Dict[str, List]) -> List[Dict]:
        """Generate recommendations for anchor text uniqueness issues"""
        recommendations = []

        non_unique_anchors = anchor_issues.get('non_unique_anchors', [])

        for issue in non_unique_anchors:
            anchor_text = issue['anchor_text']
            unique_destinations = issue['unique_destinations']
            severity = issue['severity']

            priority = 'critical' if severity == 'high' else 'high'

            recommendations.append({
                'type': 'anchor_uniqueness',
                'priority': priority,
                'impact': 'high',
                'title': f'Fix non-unique anchor text: "{anchor_text}"',
                'description': f'Anchor text "{anchor_text}" used for {unique_destinations} different destinations',
                'action_items': [
                    f'Create unique anchor text for each destination',
                    f'Use descriptive, specific anchor text for each link',
                    f'Avoid using identical anchor text for different pages'
                ],
                'affected_urls': [link['source_url'] for link in issue['links']],
                'estimated_seo_impact': 'High - Improves user experience and search engine understanding'
            })

        return recommendations

    def _generate_optimization_recommendations(self, optimization_scores: Dict[str, Dict]) -> List[Dict]:
        """Generate recommendations based on optimization scores"""
        recommendations = []

        poor_performers = []
        for url, scores in optimization_scores.items():
            if scores.get('overall', 100) < 60:
                poor_performers.append((url, scores))

        # Sort by worst performers
        poor_performers.sort(key=lambda x: x[1].get('overall', 100))

        for url, scores in poor_performers[:10]:  # Top 10 worst performers
            recommendations.append({
                'type': 'optimization',
                'priority': 'medium',
                'impact': 'medium',
                'title': f'Optimize anchor text on {url.split("/")[-1] or "page"}',
                'description': f'Anchor text optimization score: {scores.get("overall", 0):.1f}/100',
                'action_items': [
                    'Review and improve anchor text specificity',
                    'Ensure anchor text matches target page content',
                    'Use natural, descriptive language'
                ],
                'affected_urls': [url],
                'estimated_seo_impact': 'Medium - Improves link relevance and user experience'
            })

        return recommendations

    def _generate_site_recommendations(self, site_summary: Dict) -> List[Dict]:
        """Generate site-wide recommendations"""
        recommendations = []

        # Check overall site health
        total_links = site_summary.get('total_internal_links', 0)
        duplicate_percentage = site_summary.get('duplicate_percentage', 0)
        unique_anchor_percentage = site_summary.get('unique_anchor_percentage', 100)

        if duplicate_percentage > 10:
            recommendations.append({
                'type': 'site_wide',
                'priority': 'critical',
                'impact': 'high',
                'title': 'High duplicate link percentage detected',
                'description': f'{duplicate_percentage:.1f}% of internal links are duplicates',
                'action_items': [
                    'Audit all pages for duplicate internal links',
                    'Implement consistent internal linking guidelines',
                    'Set up regular monitoring for duplicate link prevention'
                ],
                'affected_urls': ['Site-wide'],
                'estimated_seo_impact': 'High - Significant link equity dilution risk'
            })

        if unique_anchor_percentage < 80:
            recommendations.append({
                'type': 'site_wide',
                'priority': 'high',
                'impact': 'high',
                'title': 'Low anchor text uniqueness',
                'description': f'Only {unique_anchor_percentage:.1f}% of anchor texts are unique',
                'action_items': [
                    'Create unique anchor text for each internal link',
                    'Develop anchor text guidelines for content creators',
                    'Audit existing anchor texts for uniqueness'
                ],
                'affected_urls': ['Site-wide'],
                'estimated_seo_impact': 'High - Improves search engine understanding'
            })

        return recommendations

    def create_action_plan(self, recommendations: List[Dict]) -> pd.DataFrame:
        """Create a structured action plan from recommendations"""
        action_items = []

        for rec in recommendations:
            for action in rec.get('action_items', []):
                action_items.append({
                    'Priority': rec['priority'].title(),
                    'Type': rec['type'].replace('_', ' ').title(),
                    'Action Item': action,
                    'Impact': rec['impact'].title(),
                    'SEO Impact': rec.get('estimated_seo_impact', 'Medium'),
                    'Affected Pages': ', '.join(rec.get('affected_urls', [])[:3])  # Limit to 3
                })

        return pd.DataFrame(action_items)
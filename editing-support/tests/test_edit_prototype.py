#!/usr/bin/env python3
"""Tests for the English edit-suggestion prototype (offline; uses cached products)."""
import copy
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent  # editing-support/
sys.path.insert(0, str(ROOT))

import wikitext_render as wr  # noqa: E402
from common import RUN  # noqa: E402
from validate import check, norm  # noqa: E402
import select_pages  # noqa: E402

HAVE_RUN = (RUN / 'selection.json').exists() and (RUN / 'evidence').exists()


class Render(unittest.TestCase):
    def test_focal_and_paired_markers(self):
        wt = ('Claim one.<ref name="a">{{cite journal |last1=Smith |date=May 3, 2010 |title=Orig |doi=10.1/ORIG}}</ref> '
              'Claim two.<ref>{{cite journal |last1=Jones |year=2015 |title=Rep |doi=10.1/rep}}</ref> '
              'Reuse.<ref name="a" />')
        out = wr.plain(wt, wr.named_refs(wt), ['10.1/orig'], ['10.1/rep'])
        self.assertEqual(out.count('[FOCAL REF: Smith (2010)'), 2)
        self.assertIn('[PAIRED REF: Jones (2015)', out)

    def test_named_reuse_positions(self):
        wt = 'A.<ref name="x">{{cite journal|doi=10.5/abc}}</ref> B.<ref name=x/> C.<ref name="x" />'
        self.assertEqual(wr.ref_names_with(wt, '10.5/ABC'), ['x'])
        self.assertEqual(len(wr.named_ref_reuses(wt, 'x')), 2)

    def test_quote_template_and_piped_links_survive(self):
        wt = '{{quote|They can "[[Fake it till you make it|fake it]]" daily.}}'
        self.assertIn('fake it', wr.plain(wt))

    def test_comments_removed(self):
        self.assertNotIn('hidden', wr.plain('Visible <!-- hidden doi:10.1/x --> text'))

    def test_section_bounds(self):
        t = 'lead\n== A ==\nx\n=== A1 ===\ny\n== B ==\nz'
        name, s, e = wr.section_bounds(t, t.index('y'))
        self.assertEqual(name, 'A1')
        self.assertTrue(t[s:e].strip().endswith('y'))


@unittest.skipUnless(HAVE_RUN, 'prototype run products not present')
class Grounding(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sel = json.loads((RUN / 'selection.json').read_text())['pages']
        # A packet whose original is abstract-only, so evidence-level overclaiming can be tested.
        cid = next(s['packet_id'] for s in cls.sel if json.loads((RUN / 'evidence' / s['packet_id'] / 'packet.json')
                   .read_text())['original']['source']['evidence_level'] == 'abstract')
        cls.pk = json.loads((RUN / 'evidence' / cid / 'packet.json').read_text())
        o = next(x for x in cls.pk['occurrences'] if x['doi_role'].startswith('original'))
        src = cls.pk['original']['source']
        quote = norm(o['paragraph_plain'])[:0] or o['paragraph_plain'].split('[')[0].strip()[:120]
        cls.good = {
            'card_id': cid,
            'claim_sites': [{'occurrence': 1, 'section': o['section'], 'visible_claim_quote': quote,
                             'is_visible_claim': len(norm(quote)) >= 40, 'note': ''}],
            'article_scope': 'broad_topic', 'citation_function': 'unclear',
            'specific_study_match': {'status': 'uncertain', 'note': ''},
            'existing_acknowledgement': {'status': 'unclear', 'note': ''},
            'evidence_used': [{'doi': src['doi'], 'role': 'original', 'evidence_level': 'metadata_only', 'excerpt': '',
                               'what_it_supports': 'identity'}],
            'assessment': 'A test assessment of sufficient length to pass the schema minimum.',
            'proposed_action': 'defer', 'queue_recommendation': 'defer', 'rationale': 'Test rationale text here.',
            'draft': {'status': 'not_applicable', 'location': '', 'operation': 'none', 'target_text': '',
                      'wording': '', 'citations': [], 'withheld_reason': 'test'},
            'content_points': [], 'alternatives': [], 'uncertainties': [], 'required_checks': ['Decide whether one sentence is due weight here.'],
            'confidence': 'low', 'flags': {'blp': True, 'medrs': False, 'other': ''}, 'verifications': [],
            'edit_strength': 'none'}

    def test_selection_has_distinct_pages_and_is_deterministic(self):
        pages = [s['pageid'] for s in self.sel]
        self.assertEqual(len(pages), len(set(pages)))
        packets = [p for p in json.loads(select_pages.PACKETS.read_text()) if p['language'] == 'en']
        again = select_pages.select(select_pages.features(packets), len(self.sel))
        self.assertEqual([r['packet_id'] for r in again], [s['packet_id'] for s in self.sel])

    def test_selection_is_outcome_blind(self):
        # Permuting outcome labels must not change which packets are chosen.
        packets = [p for p in json.loads(select_pages.PACKETS.read_text()) if p['language'] == 'en']
        flipped = copy.deepcopy(packets)
        swap = {'failed': 'successful', 'successful': 'failed'}
        for p in flipped:
            for q in p['pairs']:
                q['outcome'] = swap.get(q['outcome'], q['outcome'])
        a = select_pages.select(select_pages.features(packets), 52)
        b = select_pages.select(select_pages.features(flipped), 52)
        self.assertEqual([r['packet_id'] for r in a], [r['packet_id'] for r in b])

    def test_valid_minimal_draft_passes(self):
        errors, _ = check(self.good, self.pk)
        self.assertEqual(errors, [])

    def test_invented_excerpt_fails(self):
        d = copy.deepcopy(self.good)
        d['evidence_used'][0].update(excerpt='This sentence was invented and appears in no cached source text.',
                                     evidence_level='metadata_only')
        errors, _ = check(d, self.pk)
        self.assertTrue(any('excerpt not verbatim' in e for e in errors))

    def test_overclaimed_evidence_level_fails(self):
        d = copy.deepcopy(self.good)
        lvl = self.pk['original']['source']['evidence_level']
        if lvl == 'full_text':
            self.skipTest('original has full text')
        d['evidence_used'][0]['evidence_level'] = 'full_text'
        errors, _ = check(d, self.pk)
        self.assertTrue(any('claims full_text' in e for e in errors))

    def test_invented_claim_quote_fails(self):
        d = copy.deepcopy(self.good)
        d['claim_sites'][0].update(visible_claim_quote='The article states something it never actually says anywhere.',
                                   is_visible_claim=True)
        errors, _ = check(d, self.pk)
        self.assertTrue(any('claim quote not found' in e for e in errors))

    def test_unknown_doi_in_draft_fails(self):
        d = copy.deepcopy(self.good)
        d['draft'].update(status='provided', operation='insert_after', wording='Text [cite: 10.9999/not-real]',
                          citations=['10.9999/not-real'])
        errors, _ = check(d, self.pk)
        self.assertTrue(any('outside' in e for e in errors))

    def test_flora_as_source_fails(self):
        d = copy.deepcopy(self.good)
        d['draft'].update(status='provided', operation='insert_after', wording='According to FLoRA, it failed.',
                          citations=[])
        errors, _ = check(d, self.pk)
        self.assertTrue(any('FLoRA' in e for e in errors))

    def test_invented_number_warns(self):
        d = copy.deepcopy(self.good)
        d['draft'].update(status='provided', operation='insert_after', wording='A study of 98765 people found this.',
                          citations=[self.pk['original']['doi']])
        _, warnings = check(d, self.pk)
        self.assertTrue(any('98765' in w for w in warnings))

    def test_review_override_and_occurrence_merge(self):
        from build_site import apply_review, merge_occurrences
        final = apply_review(self.good, {'overrides': {'queue_recommendation': 'retain'}})
        self.assertEqual(final['queue_recommendation'], 'retain')
        self.assertEqual(self.good['queue_recommendation'], 'defer')  # draft itself unchanged
        o = self.pk['occurrences'][0]
        merged = merge_occurrences([o, dict(o, doi_role='original (named-reference reuse)')])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]['numbers'], [1, 2])

    def test_invented_verification_quote_fails(self):
        d = copy.deepcopy(self.good)
        d['verifications'] = [{'claim': 'The study had 9999 participants.', 'source': self.pk['original']['doi'],
                               'result': 'confirmed', 'quote': 'This sentence appears in no source we read at all.',
                               'evidence_level': 'metadata_only'}]
        errors, _ = check(d, self.pk)
        self.assertTrue(any('verification quote not verbatim' in e for e in errors))

    def test_checking_chores_for_humans_fail(self):
        d = copy.deepcopy(self.good)
        d['required_checks'] = ['Confirm in the abstract that the sample was 120 people.']
        errors, _ = check(d, self.pk)
        self.assertTrue(any('chore' in e for e in errors))

    def test_schema_rejects_unknown_action(self):
        d = copy.deepcopy(self.good)
        d['proposed_action'] = 'insert_failure_sentence'
        errors, _ = check(d, self.pk)
        self.assertTrue(errors and errors[0].startswith('schema'))

    def test_all_built_drafts_pass_grounding(self):
        assign = json.loads((RUN / 'route_assignment.json').read_text()) if (RUN / 'route_assignment.json').exists() else None
        if not assign:
            self.skipTest('no route assignment yet')
        from build_site import build_items
        cards, _ = build_items()
        failing = [(c['page']['title'], c['validation']['errors']) for c in cards if c['validation']['errors']]
        self.assertEqual(failing, [])

    def test_pages_cover_every_study_and_drafts_have_no_placeholders(self):
        from build_site import build_items, build_pages
        items, missing = build_items()
        self.assertEqual(missing, [])
        pages = build_pages(items)
        packets = [p for p in json.loads(select_pages.PACKETS.read_text()) if p['language'] == 'en']
        for pg in pages:
            expected = {p['packet_id'] for p in packets if str(p['pageid']) == pg['page_id']}
            self.assertEqual({i['card_id'] for i in pg['items']}, expected, pg['page']['title'])
        for it in items:
            self.assertTrue(it['suggestion'].get('verifications'), it['page']['title'] + ': no verifications')
            self.assertFalse([e for e in it['validation']['errors'] if 'chore' in e], it['page']['title'])
            self.assertNotIn('needs source', json.dumps(it['suggestion']).lower(), it['page']['title'])
            self.assertFalse([w for w in it['validation']['warnings'] if w.startswith('open-ended')], it['page']['title'])

    def test_packets_cache_retrieval_dates_and_revisions(self):
        for s in self.sel:
            pk = json.loads((RUN / 'evidence' / s['packet_id'] / 'packet.json').read_text())
            self.assertTrue(pk['page']['frozen_revid'])
            self.assertIn('checked_at', pk['live_check'])
            for src in [pk['original']['source']] + [r['source'] for r in pk['replications']]:
                self.assertTrue(src['retrieved_at'])
                self.assertIn(src['evidence_level'], ('full_text', 'abstract', 'metadata_only'))
                if src['evidence_level'] == 'full_text':
                    self.assertTrue((RUN / src['fulltext_path']).exists())


class CardText(unittest.TestCase):
    def test_author_year_labels(self):
        from build_site import author_year
        self.assertEqual(author_year(dict(authors=['Eric J. Johnson', 'Daniel Goldstein'], year=2003)), 'Johnson & Goldstein (2003)')
        self.assertEqual(author_year(dict(authors=['John Bargh', 'Mark Chen', 'Lara Burrows'], year=1996)), 'Bargh et al. (1996)')
        self.assertEqual(author_year(dict(authors=['John\xa0R. Lott, Jr.', 'David B. Mustard'], year=1997)), 'Lott & Mustard (1997)')
        self.assertEqual(author_year(dict(authors=["European Alzheimer's Disease Initiative (EADI)", 'J Lambert', 'X Y'],
                                          year=2013)), 'EADI et al. (2013)')
        self.assertEqual(author_year(dict(authors=['Jan C. van Ours'], year=2026)), 'van Ours (2026)')

    def test_gist_keeps_abbreviations_and_adds_a_short_opening(self):
        from build_site import split_gist
        first, rest = split_gist('Bargh et al. (1996) is cited in the lead for a claim about walking speed that it does not make, and the later replication failed. '
                                 'A second sentence. A third.')
        self.assertTrue(first.endswith('replication failed.'))
        self.assertEqual(rest, 'A second sentence. A third.')
        self.assertEqual(split_gist('The article is accurate. The replication agrees. More.'),
                         ('The article is accurate. The replication agrees.', 'More.'))

    def test_no_change_relabelling_rule(self):
        from build_site import replication_bears_on_claim
        it = dict(suggestion=dict(citation_function='current_empirical_support',
                                  specific_study_match=dict(status='matched'), existing_acknowledgement=dict(status='no')),
                  replications=[dict(flora_outcome='failed')])
        self.assertTrue(replication_bears_on_claim(it))
        for change in [('citation_function', 'historical_attribution'), ('specific_study_match', dict(status='mismatch')),
                       ('existing_acknowledgement', dict(status='yes'))]:
            alt = copy.deepcopy(it)
            alt['suggestion'][change[0]] = change[1]
            self.assertFalse(replication_bears_on_claim(alt), change)
        alt = copy.deepcopy(it)
        alt['replications'] = [dict(flora_outcome='successful')]
        self.assertFalse(replication_bears_on_claim(alt))

    def test_label_overrides_name_no_change_cards(self):
        if not HAVE_RUN:
            self.skipTest('no run')
        from build_site import build_items
        items, _ = build_items()  # raises on a stale override
        ids = {o['card_id'] for o in json.loads((ROOT / 'label_overrides.json').read_text())}
        flagged = {i['card_id'] for i in items if i.get('judgement_basis')}
        self.assertTrue(ids <= flagged)
        self.assertTrue(all(i['suggestion']['proposed_action'] == 'no_change' for i in items if i.get('judgement_basis')))

    def test_every_shown_source_has_a_label(self):
        from build_site import build_items, item_dois, source_labels
        items, _ = build_items()
        labels, missing = source_labels(items)
        self.assertEqual([d for c in items for d in item_dois(c) if d not in labels], [])
        self.assertEqual(len(set(v['label'] for v in labels.values())), len(labels))


def v6_suggestion(scope='broad_topic', use='current_empirical_support', states='as_fact', relies=True, reps=()):
    """A minimal brief-v6 suggestion for the tier rule: reps are (bears, result, on_page, accurate[, method]) tuples."""
    return dict(brief_version='v6', proposed_action='no_change', edit_strength='none', article_scope=scope,
                citation_function=use, article_use=dict(states_finding=states, relies_as_evidence=relies, note=''),
                replications_assessed=[dict(doi=f'10.1/{i}', method=(m or ['replication'])[0],
                                            tested_result='cited_result' if b != 'none' else 'other_result_same_paper',
                                            bears_on_article_claim=b, result_vs_article_claim=r, already_on_page=o,
                                            page_quote='' if o == 'no' else 'x' * 40, report_accurate=acc, note='')
                                       for i, (b, r, o, acc, *m) in enumerate(reps)])


class NoChangeTiers(unittest.TestCase):
    """Brief v6 tier rule (#9): the three calls once made by hand, and the clear cases, follow from coded fields."""

    def tier(self, **kw):
        from build_site import no_change_tier
        return no_change_tier(v6_suggestion(**kw))

    def test_former_hand_calls_are_judgement_calls(self):
        # Functional accounts of emotion: another experiment from the same paper bears indirectly and fails.
        self.assertEqual(self.tier(use='example', states='attributed', reps=[('indirect', 'fails', 'no', None)] * 3),
                         'judgement_call')
        # Jan Eeckhout and Lise Vesterlund: biographies that state the finding; the replication qualifies it.
        for states in ('as_fact', 'attributed'):
            self.assertEqual(self.tier(scope='biography_history', use='historical_attribution', states=states, relies=False,
                                       reps=[('direct', 'qualifies', 'no', None)]), 'judgement_call')

    def test_confirming_replication_of_relied_claim_is_a_judgement_call(self):
        self.assertEqual(self.tier(scope='list_or_bibliography', reps=[('direct', 'confirms', 'no', None)]), 'judgement_call')
        # The history shortcut needs relies_as_evidence false.
        self.assertEqual(self.tier(use='example', relies=True, reps=[('direct', 'confirms', 'no', None)]), 'judgement_call')

    def test_clear_cases_are_likely_no_change(self):
        # Named without its finding (Deniz Başkent, Heejung Kim), even if the study cannot be identified.
        self.assertEqual(self.tier(scope='biography_history', use='bibliography_listing', states='no', relies=False,
                                   reps=[('unclear', 'not_determinable', 'no', None)]), 'likely_no_change')
        # The replication tested something the article does not rely on (CASS4, Outgroup favoritism).
        self.assertEqual(self.tier(reps=[('none', 'fails', 'no', None)] * 2), 'likely_no_change')
        # Cited for history, and the replication confirms (TCF7L2, Timeline of psychology).
        self.assertEqual(self.tier(use='historical_attribution', states='attributed', relies=False,
                                   reps=[('direct', 'confirms', 'no', None)]), 'likely_no_change')
        # The article reports the result only as disputed and does not rely on it.
        self.assertEqual(self.tier(states='reported_as_disputed', relies=False, reps=[('direct', 'fails', 'no', None)]),
                         'likely_no_change')

    def test_confirming_reproduction_is_likely_no_change(self):
        # Re-running the original analyses on the original data (Outgroup favoritism): the group's call on #9.
        self.assertEqual(self.tier(reps=[('direct', 'confirms', 'no', None, 'reproduction')]), 'likely_no_change')
        # A failed reproduction, or one beside a confirming new-data replication, stays a judgement call.
        self.assertEqual(self.tier(reps=[('direct', 'fails', 'no', None, 'reproduction')]), 'judgement_call')
        self.assertEqual(self.tier(reps=[('direct', 'confirms', 'no', None, 'reproduction'), ('direct', 'confirms', 'no', None)]),
                         'judgement_call')

    def test_unclear_relevance_is_not_likely_no_change(self):
        self.assertEqual(self.tier(reps=[('unclear', 'not_determinable', 'no', None)]), 'judgement_call')

    def test_already_covered(self):
        self.assertEqual(self.tier(reps=[('direct', 'fails', 'cited', True)]), 'already_covered')
        self.assertEqual(self.tier(scope='list_or_bibliography', use='historical_attribution', relies=False,
                                   reps=[('none', 'fails', 'reported_in_prose', True)]), 'already_covered')
        # Inaccurate or partial coverage is not covered; an inaccurate report is always a judgement call.
        self.assertEqual(self.tier(reps=[('direct', 'fails', 'cited', False)]), 'judgement_call')
        self.assertEqual(self.tier(states='no', relies=False, reps=[('none', 'fails', 'reported_in_prose', False)]),
                         'judgement_call')
        self.assertEqual(self.tier(reps=[('direct', 'fails', 'cited', True), ('direct', 'fails', 'no', None)]),
                         'judgement_call')

    def test_rule_ignores_flora_outcome_codes(self):
        import inspect
        from build_site import no_change_tier
        self.assertNotIn('flora_outcome', inspect.getsource(no_change_tier))


@unittest.skipUnless(HAVE_RUN, 'prototype run products not present')
class ValidateV6(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Grounding.setUpClass()
        cls.pk = Grounding.pk
        d = copy.deepcopy(Grounding.good)
        d.pop('confidence')
        base = v6_suggestion(reps=[('direct', 'fails', 'no', None)] * len(cls.pk['replications']))
        for r, pr in zip(base['replications_assessed'], cls.pk['replications']):
            r['doi'] = pr['doi']
        d.update(brief_version='v6', article_use=base['article_use'], replications_assessed=base['replications_assessed'],
                 no_change_basis='not_applicable', existing_acknowledgement={'status': 'no', 'note': ''})
        cls.good = d

    def test_valid_v6_draft_passes(self):
        errors, _ = check(self.good, self.pk)
        self.assertEqual(errors, [])

    def test_v5_shape_without_version_uses_v5_schema(self):
        errors, _ = check(Grounding.good, self.pk)
        self.assertEqual(errors, [])

    def test_page_quote_required_when_on_page(self):
        d = copy.deepcopy(self.good)
        d['replications_assessed'][0].update(already_on_page='cited', report_accurate=True, page_quote='')
        errors, _ = check(d, self.pk)
        self.assertTrue(any('page_quote' in e for e in errors))

    def test_source_quote_must_come_from_the_source(self):
        d = copy.deepcopy(self.good)
        quote = self.good['claim_sites'][0]['visible_claim_quote']
        d['verifications'] = [dict(claim='The original study reports this result.', source=self.pk['original']['doi'],
                                   result='confirmed', quote=quote, evidence_level='metadata_only')]
        errors, _ = check(d, self.pk)
        self.assertTrue(any('not verbatim' in e for e in errors))
        d['verifications'][0]['claim'] = 'Wikipedia article: states this result.'
        errors, _ = check(d, self.pk)
        self.assertFalse(any('not verbatim' in e for e in errors))

    def test_missing_replication_fails(self):
        d = copy.deepcopy(self.good)
        d['replications_assessed'][0]['doi'] = '10.9999/other'
        errors, _ = check(d, self.pk)
        self.assertTrue(any('replications_assessed must list' in e for e in errors))

    def test_report_accuracy_must_match_on_page(self):
        d = copy.deepcopy(self.good)
        d['replications_assessed'][0]['report_accurate'] = True
        errors, _ = check(d, self.pk)
        self.assertTrue(any('report_accurate' in e for e in errors))

    def test_no_change_basis_and_alternative_target(self):
        d = copy.deepcopy(self.good)
        d['alternatives'] = [dict(type='belongs_elsewhere', action='Add the replication there.', when='', target_article='')]
        d['no_change_basis'] = 'confirms_claim'
        errors, _ = check(d, self.pk)
        self.assertTrue(any('target_article' in e for e in errors))
        self.assertTrue(any('no_change_basis' in e for e in errors))

    def test_bare_article_wording_warns(self):
        d = copy.deepcopy(self.good)
        d['rationale'] = 'The article already reports this replication.'
        _, warnings = check(d, self.pk)
        self.assertTrue(any('Wikipedia article' in w for w in warnings))
        d['rationale'] = "The Wikipedia article already reports this replication, saying 'the article'."
        _, warnings = check(d, self.pk)
        self.assertFalse(any('Wikipedia article' in w for w in warnings))


class Prefilter(unittest.TestCase):
    def test_detects_doi_and_title(self):
        from prefilter import detect
        text = 'x {{cite journal|title=A Direct Replication of the Classic Door-in-the-Face Study|doi=10.1/ABC}} y'
        self.assertEqual(detect('10.1/abc', '', text), 'doi')
        self.assertEqual(detect('10.1/zzz', 'A direct replication of the classic door in the face study', text), 'title')
        self.assertIsNone(detect('10.1/zzz', 'Registered Replication', text))  # short titles are not matched
        self.assertIsNone(detect('10.1/ab', '', text))  # a prefix of a longer DOI is not a match

    def test_further_reading_does_not_count(self):
        from prefilter import detect, visible
        page = 'Body {{cite journal|doi=10.1/a}}\n== Further reading ==\n* {{cite journal|doi=10.1/b}}\n=== Sub ===\n* 10.1/c\n== References ==\n10.1/d'
        found = {d: detect(d, '', visible(page)) for d in ['10.1/a', '10.1/b', '10.1/c', '10.1/d']}
        self.assertEqual(found, {'10.1/a': 'doi', '10.1/b': None, '10.1/c': None, '10.1/d': 'doi'})


class TwoRunTier(unittest.TestCase):
    def test_draft_tier_only_for_v6_no_change(self):
        from build_site import draft_tier
        self.assertEqual(draft_tier(v6_suggestion(reps=[('none', 'fails', 'no', None)])), 'likely_no_change')
        self.assertIsNone(draft_tier(dict(v6_suggestion(), proposed_action='contextualise', edit_strength='fix')))
        self.assertIsNone(draft_tier({'proposed_action': 'no_change', 'edit_strength': 'none'}))


class NoWritePaths(unittest.TestCase):
    def test_no_wikimedia_write_calls(self):
        forbidden = ['action=edit', "'action': 'edit'", 'action=wbeditentity', 'quickstatements', 'csrf']
        for p in list(ROOT.glob('*.py')) + list((ROOT / 'site').glob('*.js')):
            text = p.read_text().lower()
            for f in forbidden:
                self.assertNotIn(f, text, f'{p} contains {f}')

    def test_no_outcome_to_sentence_mapping(self):
        text = (ROOT / 'select_pages.py').read_text()
        self.assertNotIn("sorted(rows, key=lambda r: r['outcomes']", text)
        for p in ROOT.glob('*.py'):
            self.assertNotIn('failed to replicate', p.read_text().lower(), f'{p} hard-codes outcome wording')


if __name__ == '__main__':
    unittest.main(verbosity=2)

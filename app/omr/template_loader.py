import json
from pathlib import Path
ROOT = Path(__file__).parent

def load_template(template_id='opi_fundamental_2026'):
    if template_id != 'opi_fundamental_2026':
        raise ValueError('Modelo de cartão desconhecido.')
    try:
        t = json.loads((ROOT/'templates'/f'{template_id}.json').read_text())
        assert t['questions']['count'] == 30 and len(t['questions']['regions']) == 30
        assert t['cpf']['digits'] == len(t['cpf']['cells']) == 11
        assert t['normalized_width'] > 0 and t['normalized_height'] > 0
        assert t['id'] == template_id
        assert t['questions']['alternatives'] == list('ABCDE')
        assert [q['number'] for q in t['questions']['regions']] == list(range(1,31))
        for q in t['questions']['regions']:
            assert [b['answer'] for b in q['bubbles']] == list('ABCDE')
        thresholds=t['thresholds']
        assert 0 < thresholds['blank_max'] < thresholds['multiple_mark'] <= thresholds['min_fill'] < 1
        assert 0 < thresholds['min_difference'] < 1
        for r in [t['cpf']['region']] + t['cpf']['cells'] + [b for q in t['questions']['regions'] for b in q['bubbles']]:
            assert all(0 <= r[k] <= 1 for k in ('x','y','width','height'))
            assert r['width'] > 0 and r['height'] > 0
            assert r['x']+r['width'] <= 1 and r['y']+r['height'] <= 1
        return t
    except (OSError, KeyError, AssertionError, TypeError, json.JSONDecodeError) as e:
        raise ValueError('Template inválido. Contate a organização.') from e

def pixel_rect(region, width, height):
    x,y,w,h = [round(region[k]*s) for k,s in [('x',width),('y',height),('width',width),('height',height)]]
    return x,y,w,h

def crop(image, region, inset=0):
    x,y,w,h = pixel_rect(region,image.shape[1],image.shape[0])
    return image[y+inset:y+h-inset,x+inset:x+w-inset]

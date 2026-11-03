"""Read experiment JSON files and create a standalone HTML report.

Usage: python src/visualize.py results/<session> --output results/report.html
Graphs are shown for instances in a 'dummy' directory. Node labels start at 1.
The circular layout is schematic, not a representation of physical distances.
"""

import argparse
import json
from pathlib import Path


PAGE = r'''<!doctype html>
<html lang="pt-BR"><meta charset="utf-8">
<title>Experimentos de localização de hubs</title>
<style>
body{font:16px system-ui;margin:32px auto;max-width:1200px;padding:0 20px;color:#182b3a;background:#f4f7fa}
table{border-collapse:collapse;width:100%;background:white}th,td{padding:9px;text-align:left;border-bottom:1px solid #ddd}
.scroll{overflow:auto}select{padding:8px;max-width:100%;margin:8px}svg{background:white;border:1px solid #ccd7df;width:100%;max-height:620px}
.hub{fill:#c65d13}.node{fill:#246b8e}text{font:15px system-ui;fill:white;text-anchor:middle;dominant-baseline:middle}
#detail{white-space:pre-wrap}small{color:#465867}label{display:block}
</style>
<h1>Experimentos de localização de hubs</h1>
<p>Custos e tempos por execução. Soluções viáveis sem prova de otimalidade são identificadas pelo estado da solução.</p>
<div class="scroll"><table><thead><tr><th>Instância</th><th>p</th><th>r</th><th>α</th><th>Estado</th><th>Solução</th><th>Custo</th><th>Montagem (s)</th><th>Solver (s)</th><th>Total (s)</th></tr></thead><tbody id="rows"></tbody></table></div>
<h2>Soluções das instâncias dummy</h2>
<label>Execução <select id="run"></select></label>
<label>Fluxo origem → destino <select id="route"></select></label>
<p><small>Hubs em laranja; demais nós em azul. Ligações tracejadas: alocações. Setas: rotas do fluxo selecionado. Posições circulares esquemáticas; rótulos dos nós começam em 1.</small></p>
<svg id="graph" viewBox="0 0 900 620" role="img" aria-label="Grafo de hubs, alocações e rotas"></svg>
<p id="detail"></p>
<script id="data" type="application/json">__DATA__</script>
<script>
const data=JSON.parse(document.querySelector('#data').textContent);
const el=id=>document.getElementById(id), ns='http://www.w3.org/2000/svg';
const number=v=>v==null?'—':Number(v).toLocaleString('pt-BR',{maximumFractionDigits:4});
for(const d of data){const tr=document.createElement('tr');
 for(const v of [d.instance_name,d.p,d.r,d.alpha,d.status,d.solution_status,number(d.objective),number(d.build_seconds),number(d.solve_seconds),number(d.total_seconds)]){const td=document.createElement('td');td.textContent=v??'—';tr.append(td)}el('rows').append(tr)}
const runs=data.filter(d=>d.is_dummy&&d.has_solution);
for(const [idx,d] of runs.entries()){const o=document.createElement('option');o.value=idx;o.textContent=`${d.instance_name}: p=${d.p}, r=${d.r}, α=${d.alpha} — custo ${number(d.objective)}`;el('run').append(o)}
function svg(tag,attrs){const e=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,v);return e}
function choose(){el('route').replaceChildren();const d=runs[el('run').value];if(!d)return;
 const all=document.createElement('option');all.value='';all.textContent='Somente alocações';el('route').append(all);
 const pairs=new Set(d.routes.map(x=>`${x[0]},${x[1]}`));for(const pair of pairs){const o=document.createElement('option');o.value=pair;o.textContent=pair.split(',').map(x=>Number(x)+1).join(' → ');el('route').append(o)}draw()}
function draw(){const g=el('graph');g.replaceChildren();const d=runs[el('run').value];if(!d){el('detail').textContent='Nenhuma solução dummy disponível para desenhar.';return}
 const defs=svg('defs',{}),marker=svg('marker',{id:'arrow',viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:7,markerHeight:7,orient:'auto-start-reverse'});marker.append(svg('path',{d:'M 0 0 L 10 5 L 0 10 z',fill:'#a63258'}));defs.append(marker);g.append(defs);
 const pos=Array.from({length:d.n},(_,i)=>[450+245*Math.cos(2*Math.PI*i/d.n-Math.PI/2),310+245*Math.sin(2*Math.PI*i/d.n-Math.PI/2)]);
 function edge(a,b,active){if(a===b)return;const [x,y]=pos[a],[u,v]=pos[b],dist=Math.hypot(u-x,v-y),off=24;g.append(svg('line',{x1:x+(u-x)*off/dist,y1:y+(v-y)*off/dist,x2:u-(u-x)*off/dist,y2:v-(v-y)*off/dist,stroke:active?'#a63258':'#8295a1','stroke-width':active?3:1.5,...(active?{'marker-end':'url(#arrow)'}:{'stroke-dasharray':'6 5'})}))}
 for(const [i,k] of d.allocations)edge(i,k,false);
 const pair=el('route').value,selected=d.routes.filter(x=>`${x[0]},${x[1]}`===pair);
 for(const [i,j,k,l] of selected){edge(i,k,true);edge(k,l,true);edge(l,j,true)}
 for(let i=0;i<d.n;i++){const [cx,cy]=pos[i];g.append(svg('circle',{cx,cy,r:23,class:d.hubs.includes(i)?'hub':'node'}));const t=svg('text',{x:cx,y:cy});t.textContent=i+1;g.append(t)}
 el('detail').textContent=`Hubs: ${d.hubs.map(i=>i+1).join(', ')}\n`+(selected.length?selected.map(([i,j,k,l,f])=>`${i+1} → ${k+1} → ${l+1} → ${j+1}: ${number(100*f)}% do fluxo`).join('\n'):'Selecione um par para destacar suas rotas.');}
el('run').addEventListener('change',choose);el('route').addEventListener('change',draw);choose();if(!runs.length)draw();
</script></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='JSON de uma execução ou pasta de resultados')
    parser.add_argument('--output', type=Path, default=Path('results/report.html'))
    args = parser.parse_args()
    files = sorted(args.input.rglob('*.json')) if args.input.is_dir() else [args.input]
    records = []
    for path in files:
        try:
            record = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(record, dict) or 'p' not in record or 'instance' not in record:
                continue
            instance = Path(record['instance'])
            record['instance_name'] = instance.stem
            record['is_dummy'] = 'dummy' in instance.parts
            records.append(record)
        except (OSError, ValueError, TypeError) as exc:
            parser.error(f'Não foi possível ler {path}: {exc}')
    if not records:
        parser.error('Nenhum resultado de experimento encontrado.')
    # Prevent embedded user-controlled paths/messages from closing the script tag.
    payload = json.dumps(records, ensure_ascii=True, allow_nan=False).replace('<', '\\u003c')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(PAGE.replace('__DATA__', payload), encoding='utf-8')
    print(f'{len(records)} execuções: {args.output.resolve()}')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Compare fusion rules on identical recorded labels, without API requests."""
import argparse
from dataclasses import replace
import gzip
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from evaluate_retrieval import evaluate
from uniagent.retrieval.corpora import read_documents
from uniagent.retrieval.lexical import LexicalIndex
from uniagent.retrieval.ranking import Hit
from uniagent.retrieval.rerank import combine
from uniagent.retrieve import write_run
from uniagent.trace import RunTrace, read_events


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('out/retrieval-evidence-fusion-control'))
    args=parser.parse_args()
    if args.output.exists():raise ValueError('Use a fresh output directory')
    root=Path(__file__).resolve().parents[1]
    for name in ('retrieval-de-spot-check','retrieval-en-spot-check','retrieval-hessian-law-de-spot-check'):
        data=root/'data/uniagent-code/cikm26/datasets'/name
        documents=list(read_documents(data/'documents.jsonl.gz'))
        positions={d.doc_id:i for i,d in enumerate(documents)}
        first={};canonical={}
        for d in documents:
            digest=hashlib.sha256(d.text.encode()).digest()
            canonical[d.doc_id]=first.setdefault(digest,d.doc_id)
        index=SimpleNamespace(config=SimpleNamespace(diversify=True),canonical=canonical,positions=positions)
        rankings={}
        with gzip.open(root/'out/retrieval-evidence-lexical/H1'/name/'run.txt.gz','rt') as f:
            for line in f:
                q,_,identifier,_,score,_=line.split()
                rankings.setdefault(q,[]).append(Hit(identifier,float(score)))
        for source in ('threshold','rrf'):
            trace_path=root/'out/retrieval-evidence-pointwise'/source/name/'run-trace.jsonl.log.gz'
            source_model=json.loads((trace_path.parent/'evaluation.json').read_text())['cost']['model']
            labels={e['case_id']:e['output']['labels'] for e in read_events(trace_path) if e['event_type']=='observation' and isinstance(e['output'],dict) and 'labels' in e['output']}
            for method in ('threshold','rrf'):
                out=args.output/f'{source}-labels-{method}'/name
                out.mkdir(parents=True)
                final=[]
                with RunTrace(out/'run-trace.jsonl.log.gz',model=source_model) as trace:
                    for q,hits in rankings.items():
                        grades=labels.get(q)
                        trace.emit('input',case_id=q,input={'source_trace':str(trace_path.relative_to(root)), 'reused_labels':grades,'fusion':method},truncate=False)
                        result=hits
                        if grades:
                            n=min(20,len(hits))
                            if method=='rrf':result=combine(hits,[grades.get(h.doc_id,0) for h in hits[:n]],'rrf')
                            else:
                                prefix=sorted(hits[:n],key=lambda h: grades.get(h.doc_id,0)<2)
                                result=[replace(h,score=hits[i].score) for i,h in enumerate(prefix)]+hits[n:]
                            prefix=LexicalIndex._diversify(index,result[:n])
                            result=[replace(h,score=hits[i].score) for i,h in enumerate(prefix)]+hits[n:]
                        trace.decision(case_id=q,output={'decision':'ranked','answer':[h.doc_id for h in result],'evidence':[]})
                        final.append((q,result))
                write_run(out/'run.txt.gz',final,'fusion-control')
                report=evaluate(data,out,root/'data/uniagent-code/cikm26/evaluation/evaluate_submission.py')
                report['reuse']={'source':source,'method':method,'new_api_calls':0,'valid_label_queries':len(labels)}
                (out/'evaluation.json').write_text(json.dumps(report,indent=2)+'\n')
                print(source,method,name,report['official'],flush=True)


if __name__=='__main__':main()

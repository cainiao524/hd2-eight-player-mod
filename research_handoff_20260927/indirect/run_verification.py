"""Run ordinary and optimized checks, then require intentional corruption to fail."""
import argparse,json,subprocess,sys
from pathlib import Path
def main():
    p=argparse.ArgumentParser();p.add_argument('--evidence',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    output=Path(a.output)
    if output.exists():raise ValueError('refusing overwrite')
    rows=[]
    for optimized in [False,True]:
        for fault in [False,True]:
            cmd=[sys.executable]+(['-O'] if optimized else [])+[str(Path(__file__).with_name('verify_indirect.py')),'--evidence',a.evidence]+(['--inject-instruction-fault'] if fault else [])
            run=subprocess.run(cmd,capture_output=True,text=True)
            ok=(run.returncode!=0) if fault else (run.returncode==0)
            rows.append({'optimized':optimized,'injected_instruction_fault':fault,'exit_code':run.returncode,'expected_status_observed':ok,'stdout':run.stdout,'stderr':run.stderr})
    output.write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
    print(json.dumps([{k:v for k,v in r.items() if k not in ('stdout','stderr')} for r in rows],indent=2))
    raise SystemExit(0 if all(r['expected_status_observed'] for r in rows) else 1)
if __name__=='__main__':main()

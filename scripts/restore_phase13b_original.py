from pathlib import Path
p=Path(__file__).with_name('run_phase13b_true_parity.py'); s=p.read_text()
s=s.replace("if f'NSE:{sym}' in account.positions and account.positions[f'NSE:{sym}'].quantity: continue", "if sym in account.positions and account.positions[f'NSE:{sym}'].quantity: continue")
s=s.replace("desired=max(0,int(target_value/(op*(1+5/10000)*(1+20/10000)))); affordable=max(0,int(account.cash/(op*(1+5/10000)*(1+20/10000)))); q=min(desired,affordable)", "q=max(0,int(target_value/(op*1.0025)))")
s=s.replace("if q<=0: continue\n   req=OrderRequest", "if q<=0: continue\n   req=OrderRequest")
Path('/tmp/phase13b_original_runner.py').write_text(s)
print('/tmp/phase13b_original_runner.py')

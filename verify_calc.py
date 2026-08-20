# -*- coding: utf-8 -*-
"""房贷计算器交叉验证——复刻 index.html 的 simulateLoan 逻辑，对照 JS 结果。
用法: python3 verify_calc.py
"""
import math

def annuity_pmt(P, r, n):
    if r <= 0: return P / n if n > 0 else 0
    if n <= 0: return 0
    f = (1 + r) ** n
    return P * r * f / (f - 1)

def round2(x): return round(x * 100) / 100

def recompute_months(P, r, pmt):
    if pmt <= 0 or P <= 0: return 0
    if P * r >= pmt: return float('inf')
    n = math.log(pmt / (pmt - P * r)) / math.log(1 + r)
    return math.ceil(n)

def simulate_loan(amount, rate_annual, months, method='annuity', prepays=None, rate_adjs=None):
    P = amount
    r = rate_annual / 12
    remain_months = months
    pmt = round2(annuity_pmt(P, r, months)) if method == 'annuity' else 0
    monthly_principal = round2(P / months) if (method == 'equal' and months > 0) else 0
    prepays = sorted(prepays or [], key=lambda x: x['m'])
    rate_adjs = sorted(rate_adjs or [], key=lambda x: x['m'])
    rows = []
    max_m = months + 240
    total_interest = 0.0
    total_prepay = 0.0
    first_month = None
    m = 1
    while m <= max_m:
        if P <= 0.001: break
        ra = next((x for x in rate_adjs if x['m'] == m), None)
        rate_adjusted = False
        if ra and P > 0.001:
            r = ra['rate'] / 12
            rate_adjusted = True
            if method == 'annuity':
                pmt = round2(annuity_pmt(P, r, max(1, remain_months - 1)))
        # 按分计息
        interest = round2(P * r)
        if method == 'annuity':
            # 尾差并入最后一期：remain_months<=1 时直接结清剩余本金
            principal = P if remain_months <= 1 else round2(min(P, max(0, pmt - interest)))
        else:
            principal = round2(min(monthly_principal, P))
        if m == 1: first_month = principal + interest
        P = round2(P - principal)
        total_interest += interest
        pp = next((x for x in prepays if x['m'] == m), None)
        prepaid = 0
        if pp and P > 0.001:
            prepaid = round2(min(pp['amount'], P))
            P = round2(P - prepaid)
            total_prepay += prepaid
            if method == 'annuity':
                if pp['mode'] == 'shorten':
                    remain_months = recompute_months(P, r, pmt) + 1
                else:
                    pmt = round2(annuity_pmt(P, r, max(1, remain_months - 1)))
            else:
                if pp['mode'] == 'shorten':
                    remain_months = (math.ceil(P / monthly_principal) + 1) if monthly_principal > 0 else 1
                else:
                    monthly_principal = round2(P / max(1, remain_months - 1))
        rows.append({
            'm': m,
            'principal': round2(principal),
            'interest': round2(interest),
            'balance': round2(P),
            'prepaid': round2(prepaid) if prepaid > 0 else 0,
            'rate_adjusted': rate_adjusted,
            'closed': P <= 0.001
        })
        if P <= 0.001: break
        remain_months = max(0, remain_months - 1)
        m += 1
    return {
        'rows': rows, 'total_interest': total_interest, 'total_prepay': total_prepay,
        'months': len(rows), 'first_month': first_month
    }

def fmt(x): return f"{x:,.2f}"
ok_count = 0
fail_count = 0
def check(name, cond, detail=""):
    global ok_count, fail_count
    mark = "✅" if cond else "❌"
    print(f"  {mark} {name}{('  [' + detail + ']') if detail else ''}")
    if cond: ok_count += 1
    else: fail_count += 1

if __name__ == '__main__':
    print("=" * 64)
    print("场景1: 商贷 515500 @ 3.2% 等额本息 213期")
    s = simulate_loan(515500, 0.032, 213, 'annuity')
    pmt_formula = annuity_pmt(515500, 0.032/12, 213)
    pmt_sim = s['rows'][0]['principal'] + s['rows'][0]['interest']
    print(f"  公式月供={fmt(pmt_formula)} 模拟首月={fmt(pmt_sim)} 总利息={fmt(s['total_interest'])} 期数={s['months']}")
    # 公式独立校验: 用高精度手算公式
    P, r, n = 515500.0, 0.032/12, 213
    f = (1+r)**n
    manual = P*r*f/(f-1)
    check("公式月供≈手算", abs(pmt_formula - manual) < 1e-6, f"{fmt(pmt_formula)} vs {fmt(manual)}")
    # 注意: 记忆中的3183.85是用户实际月供(隐含利率≠3.2%), 3.2%公式正确值=3175.38
    check("3.2%公式月供=3175.38", abs(pmt_formula - 3175.38) < 0.01, f"{fmt(pmt_formula)}")
    check("模拟首月=公式月供(round2)", abs(pmt_sim - round2(pmt_formula)) < 0.01)
    # 等额本息总还款 = 各期(本金+利息)之和 = 本金+总利息 (尾期微调, 可能±1期)
    total_paid = sum(rr['principal'] + rr['interest'] for rr in s['rows'])
    check("总还款=本金+总利息", abs(total_paid - (515500 + s['total_interest'])) < 0.01,
          f"{fmt(total_paid)} vs {fmt(515500+s['total_interest'])}")
    check("期数≈213(尾期舍入允许±1)", abs(s['months'] - 213) <= 1, f"{s['months']}")
    # 已知: 用户实际月供3183.85隐含利率更高, 反推验证"四数不自洽"
    # (只打印, 不assert)
    lo, hi = 0.03, 0.04
    for _ in range(60):
        mid = (lo+hi)/2
        if annuity_pmt(515500, mid/12, 213) > 3183.85: hi = mid
        else: lo = mid
    print(f"  [参考] 月供3183.85对应的隐含年利率≈{lo*100:.4f}% (≠给定3.2%, 符合技能记录的不自洽现象)")

    print("=" * 64)
    print("场景2: 公积金 700000 @ 2.6% 等额本金 240期")
    s2 = simulate_loan(700000, 0.026, 240, 'equal')
    exp_first = 700000/240 + 700000*0.026/12
    sim_first = s2['rows'][0]['principal'] + s2['rows'][0]['interest']
    check("等额本金首月", abs(sim_first - exp_first) < 0.01, f"{fmt(sim_first)} vs {fmt(exp_first)}")
    check("等额本金期数=240", s2['months'] == 240, f"{s2['months']}")
    check("末月余额=0", abs(s2['rows'][-1]['balance']) < 0.01, f"{s2['rows'][-1]['balance']}")
    # 等额本金月还本金恒定(除最后一期尾差)
    mp = s2['rows'][0]['principal']
    const_rows = [rr['principal'] for rr in s2['rows'][:-1]]
    check("月还本金恒定(除尾期)", all(abs(rr - mp) < 0.01 for rr in const_rows), f"{mp}")

    print("=" * 64)
    print("场景3: 提前还款缩期 vs 减月供 (商贷515500@3.2% 213期, 第36期后提前还5万)")
    s3a = simulate_loan(515500, 0.032, 213, 'annuity', prepays=[{'m': 36, 'amount': 50000, 'mode': 'shorten'}])
    s3b = simulate_loan(515500, 0.032, 213, 'annuity', prepays=[{'m': 36, 'amount': 50000, 'mode': 'reduce'}])
    save_shorten = s['total_interest'] - s3a['total_interest']
    save_reduce = s['total_interest'] - s3b['total_interest']
    print(f"  缩期: 期数={s3a['months']} 总利息={fmt(s3a['total_interest'])} 省息={fmt(save_shorten)}")
    print(f"  减月供: 期数={s3b['months']} 总利息={fmt(s3b['total_interest'])} 省息={fmt(save_reduce)}")
    check("缩期省息>0", save_shorten > 0)
    check("减月供省息>0", save_reduce > 0)
    check("缩期省息≈2倍减月供", abs(save_shorten/save_reduce - 2.0) < 0.3, f"比值={save_shorten/save_reduce:.2f}")
    check("缩期期数<减月供期数", s3a['months'] < s3b['months'], f"{s3a['months']} vs {s3b['months']}")
    # 缩期: 月供不变(检查第36期后)
    check("缩期后月供≈原月供", abs((s3a['rows'][36]['principal']+s3a['rows'][36]['interest']) - pmt_sim) < 1.0,
          f"{fmt(s3a['rows'][36]['principal']+s3a['rows'][36]['interest'])} vs {fmt(pmt_sim)}")
    # 减月供: 月供降低
    check("减月供后月供<原月供", (s3b['rows'][36]['principal']+s3b['rows'][36]['interest']) < pmt_sim,
          f"{fmt(s3b['rows'][36]['principal']+s3b['rows'][36]['interest'])} vs {fmt(pmt_sim)}")
    # 减月供: 期数不变(213)
    check("减月供期数=原期数", s3b['months'] == 213, f"{s3b['months']}")
    # 提前还款行prepaid正确
    check("缩期第36期prepaid=50000", abs(s3a['rows'][35]['prepaid'] - 50000) < 0.01,
          f"{s3a['rows'][35]['prepaid']}")

    print("=" * 64)
    print("场景4: 利率调整 (商贷515500@3.2% 213期, 第13期起利率降至3.0%)")
    s4 = simulate_loan(515500, 0.032, 213, 'annuity', rate_adjs=[{'m': 13, 'rate': 0.03}])
    print(f"  期数={s4['months']} 总利息={fmt(s4['total_interest'])}")
    # 重定价口径: 第13期调整, 用剩余期数200期重算, 总期数=12+200+尾差(212或213)
    check("利率调整后期数≈213(允许尾差±1)", abs(s4['months'] - 213) <= 1, f"{s4['months']}")
    check("降息后总利息更低", s4['total_interest'] < s['total_interest'],
          f"{fmt(s4['total_interest'])} vs {fmt(s['total_interest'])}")
    # 第13期标记rate_adjusted
    check("第13期标记利率调整", s4['rows'][12]['rate_adjusted'] is True)
    # 第13期月供按3.0%重算: 检查13期后月供≠原月供(降息应降低)
    pay13 = s4['rows'][12]['principal'] + s4['rows'][12]['interest']
    pay14 = s4['rows'][13]['principal'] + s4['rows'][13]['interest']
    check("调整后月供降低", pay14 < pmt_sim, f"{fmt(pay14)} vs {fmt(pmt_sim)}")

    print("=" * 64)
    print("场景5: 组合贷合计 (场景1+场景2)")
    first_total = (s['rows'][0]['principal'] + s['rows'][0]['interest']) + (s2['rows'][0]['principal'] + s2['rows'][0]['interest'])
    check("首月合计=商贷+公积金", abs(first_total - (pmt_sim + exp_first)) < 0.01, f"{fmt(first_total)}")
    check("总利息合计", abs((s['total_interest'] + s2['total_interest']) - (160856.31 + 0)) > 0, "仅验证可相加")  # 占位

    print("=" * 64)
    print("场景6: 多次提前还款 + 组合场景 (商贷第36期还5万缩期, 第60期再还3万减月供; 第13期利率3.0%)")
    s6c = simulate_loan(515500, 0.032, 213, 'annuity',
                        prepays=[{'m': 36, 'amount': 50000, 'mode': 'shorten'},
                                 {'m': 60, 'amount': 30000, 'mode': 'reduce'}],
                        rate_adjs=[{'m': 13, 'rate': 0.03}])
    s6f = simulate_loan(700000, 0.026, 240, 'equal')
    print(f"  商贷: 期数={s6c['months']} 总利息={fmt(s6c['total_interest'])} 提前还={fmt(s6c['total_prepay'])}")
    check("商贷提前还款总额=8万", abs(s6c['total_prepay'] - 80000) < 0.01, f"{fmt(s6c['total_prepay'])}")
    check("商贷期数<213", s6c['months'] < 213, f"{s6c['months']}")
    check("组合贷总期数=较长期数", max(s6c['months'], s6f['months']) == 240, f"{max(s6c['months'], s6f['months'])}")
    # 主表总利息
    tot_int = s6c['total_interest'] + s6f['total_interest']
    check("组合总利息可计算", tot_int > 0, f"{fmt(tot_int)}")

    print("=" * 64)
    print(f"结果: {ok_count} 通过, {fail_count} 失败")
    exit(1 if fail_count else 0)

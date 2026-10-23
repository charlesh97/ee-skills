import re,math
class Q(str):
    """quoted string atom"""
    pass
def parse(s):
    tok=re.finditer(r'"(?:[^"\\]|\\.)*"|\(|\)|[^\s()"]+',s)
    stack=[[]]
    for m in tok:
        t=m.group(0)
        if t=='(': stack.append([])
        elif t==')':
            l=stack.pop(); stack[-1].append(l)
        else:
            stack[-1].append(Q(t[1:-1]) if t.startswith('"') else t)
    return stack[0][0]
def atom(a):
    if isinstance(a,Q): return '"'+a.replace('\\','\\\\').replace('"','\\"')+'"'
    return str(a)
INLINE={'at','size','start','end','mid','center','xy','width','layer','layers','net','drill','uuid','thickness','stroke','type','color','font','justify','offset','angle','length','hatch','min_thickness','filled_areas_thickness','island_removal_mode','island_area_min','thermal_gap','thermal_bridge_width','smoothing','radius','clearance','hatch_thickness','hatch_gap','hatch_orientation','hatch_smoothing_level','hatch_smoothing_value','hatch_border_algorithm','hatch_min_hole_area','priority','descr','tags','attr','tstamp','solder_mask_margin','roundrect_rratio','locked','hide','remove_unused_layers','keep_end_layers','free','zone_connect','die_length','thermal_width','pinfunction','pintype','version','generator','generator_version','paper','name','number','mode','fill','connect_pads','keepout','copperpour','tracks','vias','pads','footprints','graphics','legacy_teardrops','pad_to_mask_clearance','allow_soldermask_bridges_in_footprints','sheetname','sheetfile','path','embedded_fonts','duplicate_pad_numbers_are_jumpers','autoplace_cost180','autoplace_cost90','solder_paste_margin','solder_paste_ratio','mirror','face','bold','italic','line_spacing'}
def ser(n,ind=0):
    if not isinstance(n,list): return atom(n)
    if all(not isinstance(c,list) for c in n):
        return '('+' '.join(atom(c) for c in n)+')'
    # simple inline: head + atoms + small lists like (xy) when head in INLINE and all children are atom-only lists
    if n[0] in INLINE and all((not isinstance(c,list)) or all(not isinstance(cc,list) for cc in c) for c in n) and n[0] not in ('fill','connect_pads','stroke','font','pts'):
        return '('+' '.join(ser(c) for c in n)+')'
    out='('+atom(n[0])
    i=1
    while i<len(n) and not isinstance(n[i],list):
        out+=' '+atom(n[i]); i+=1
    for c in n[i:]:
        out+='\n'+'\t'*(ind+1)+ser(c,ind+1)
    out+='\n'+'\t'*ind+')'
    return out
def find(l,key): return [x for x in l if isinstance(x,list) and x and x[0]==key]
def find1(l,key,default=None):
    f=find(l,key); return f[0] if f else default
def rot(x,y,a):
    a=math.radians(a); c,s=math.cos(a),math.sin(a)
    return x*c - y*s, x*s + y*c
def fp_ref(fp): return [p for p in find(fp,'property') if p[1]=='Reference'][0][2]
def fp_at(fp):
    at=find1(fp,'at'); return float(at[1]),float(at[2]),(float(at[3]) if len(at)>3 else 0.0)
def pads_abs(fp):
    fx,fy,fr=fp_at(fp); out=[]
    for pad in find(fp,'pad'):
        pat=find1(pad,'at'); px,py=float(pat[1]),float(pat[2]); pr=float(pat[3]) if len(pat)>3 else 0.0
        sz=find1(pad,'size'); dx,dy=rot(px,py,-fr)
        net=find1(pad,'net'); 
        out.append(dict(name=str(pad[1]),type=pad[2],shape=pad[3],x=fx+dx,y=fy+dy,rot=pr,w=float(sz[1]),h=float(sz[2]),net=(str(net[1]) if net else None),layers=[str(l) for l in find1(pad,'layers')[1:]],
                        rr=(float(find1(pad,'roundrect_rratio')[1]) if find1(pad,'roundrect_rratio') else 0), drill=(float(find1(pad,'drill')[1]) if find1(pad,'drill') else None)))
    return out
def load(p): return parse(open(p).read())
def save(pcb,p): open(p,'w').write(ser(pcb)+'\n')

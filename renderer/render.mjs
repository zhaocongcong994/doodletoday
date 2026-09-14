import satori from 'satori';
import { Resvg } from '@resvg/resvg-js';
import fs from 'node:fs';
const font=fs.readFileSync(new URL('./fonts/NotoSansSC-Regular.ttf',import.meta.url));
const styleRegistry=JSON.parse(fs.readFileSync(new URL('../style-registry.json',import.meta.url)));
const cardStyleIds=new Set(styleRegistry.styles.map(style=>style.id));
const el=(type,style,children,props={})=>({type,props:{style:Object.fromEntries(Object.entries(style).filter(([,v])=>v!==undefined)),children,...props}});
const box=(style,children)=>el('div',{display:'flex',...style},children);
const text=(value,size=24,style={})=>box({fontSize:size,lineHeight:1.4,...style},value);
const img=(src,width,height,style={})=>el('img',{width,height,objectFit:'contain',...style},undefined,{src,width,height});
const root=(color,bg,children)=>box({width:1080,height:1440,backgroundColor:bg,color,fontFamily:'Noto',position:'relative',overflow:'hidden',flexDirection:'column',padding:72,paddingBottom:145},children);
const line=(color)=>box({height:2,backgroundColor:color,width:'100%'},[]);
const footer=(left,right,color)=>box({position:'absolute',left:72,right:72,bottom:54,justifyContent:'space-between',color,fontSize:18,letterSpacing:2},[el('div',{fontSize:18,lineHeight:1.4},left,{'data-footer':true}),el('div',{fontSize:18,lineHeight:1.4},right,{'data-footer':true})]);
const circle=(size,left,top,color,border)=>box({position:'absolute',width:size,height:size,borderRadius:'50%',left,top,backgroundColor:color,border},[]);
function card(c){
 if(!cardStyleIds.has(c.style))throw Error('unsupported card style');
 if(c.style==='minimal')return root('#252524','#eeeee8',[
  text('今日 / PERSONA',22,{letterSpacing:5}),line('#252524'),
  text('此刻，',45,{marginTop:180}),text(c.title,Math.min(100,1100/Math.max(c.title.length/2,8)),{marginTop:15,maxWidth:880,lineHeight:1.35}),
  line('#252524'),text(c.subtitle,32,{marginTop:50,maxWidth:780}),
  box({marginTop:'auto',gap:22,flexWrap:'wrap'},c.tags.map(t=>text('# '+t,25))),footer('仅限今日有效','DoodleToday','#62635f')]);
 if(c.style==='labels')return root('#272937','#f2e9d4',[
  text('TODAY, IN THREE WORDS.',23,{letterSpacing:3}),
  text(c.title,76,{marginTop:110,lineHeight:1.25}),
  box({flexDirection:'column',alignItems:'center',marginTop:65,gap:28},c.tags.map((t,i)=>box({padding:'22px 44px',borderRadius:i===1?0:90,backgroundColor:['#d2ec7d','#bcb4e4','#f4a685'][i],border:'2px solid #272937',transform:`rotate(${[-5,4,-3][i]}deg)`},text(t,45)))),
  text(c.subtitle,32,{marginTop:75,maxWidth:820}),footer('今日人格卡','DoodleToday','#4c4d55')]);
 if(c.style==='receipt')return root('#403a31','#eee3cc',[
  box({justifyContent:'space-between',alignItems:'center'},[text('TODAY / RECEIPT',22,{letterSpacing:4}),text('NO. 24H',20,{letterSpacing:2})]),
  line('#403a31'),text('今日情绪存根',23,{marginTop:35,letterSpacing:4}),
  text(c.title,78,{marginTop:112,maxWidth:860,lineHeight:1.23,whiteSpace:'pre-wrap'}),
  box({marginTop:48,paddingTop:25,borderTop:'2px dashed #806f5d',flexDirection:'column',gap:16},[
   text(c.subtitle,30,{maxWidth:810,lineHeight:1.65}),
   text('--- 只在今天有效，请妥善保留 ---',18,{letterSpacing:2,color:'#7c6b5d'})
  ]),
  box({marginTop:'auto',gap:14,flexDirection:'column'},c.tags.map((t,i)=>box({justifyContent:'space-between',borderBottom:'1px solid #857563',paddingBottom:12},[text(`0${i+1}`,18,{letterSpacing:2,color:'#bd654c'}),text(t,26)]))),
  footer('PERSONA ARCHIVE','DoodleToday','#806f5d')]);
 if(c.style==='doodle')return root('#554c77','#fff8e8',[
  circle(430,700,105,'#ef9b8d'),circle(300,40,875,'#9dcaad'),circle(180,820,1110,'#f6d479'),
  text('TODAY’S LITTLE NOTE',22,{letterSpacing:3}),
  box({marginTop:32,padding:'16px 24px',backgroundColor:'#fffdf4',border:'2px solid #554c77',transform:'rotate(-2deg)',flexDirection:'column'},[
   text('写给现在的你',20,{letterSpacing:3,color:'#8a7aa5'}),text(c.title,72,{marginTop:28,maxWidth:850,lineHeight:1.25,whiteSpace:'pre-wrap'})
  ]),
  box({marginTop:45,gap:18,flexWrap:'wrap'},c.tags.map((t,i)=>box({padding:'14px 25px',backgroundColor:['#f6d479','#9dcaad','#ef9b8d'][i],border:'2px solid #554c77',borderRadius:8,transform:`rotate(${[-3,2,-2][i]}deg)`},text('# '+t,25)))),
  text(c.subtitle,30,{marginTop:55,maxWidth:820,lineHeight:1.65}),footer('随手记下，也算郑重','DoodleToday','#8a7aa5')]);
 if(c.style==='neon')return root('#f6ed9c','#111426',[
  circle(560,640,150,'#f165d355'),circle(420,80,780,'#57e5e333'),
  box({justifyContent:'space-between',alignItems:'center'},[text('NIGHT SIGNAL',23,{letterSpacing:5,color:'#57e5e3'}),text('00 : NOW',20,{letterSpacing:3,color:'#f6ed9c'})]),
  line('#57e5e3'),text('还亮着的部分',22,{marginTop:30,letterSpacing:4,color:'#f165d3'}),
  text(c.title,80,{marginTop:125,maxWidth:860,lineHeight:1.22,whiteSpace:'pre-wrap'}),
  text(c.subtitle,31,{marginTop:45,maxWidth:820,lineHeight:1.65,color:'#dcdef0'}),
  box({marginTop:'auto',gap:16,flexDirection:'column'},c.tags.map((t,i)=>box({padding:'13px 22px',border:`2px solid ${['#57e5e3','#f165d3','#f6ed9c'][i]}`,justifyContent:'space-between'},[text(`0${i+1}`,18,{letterSpacing:3,color:['#57e5e3','#f165d3','#f6ed9c'][i]}),text(t,26)]))),
  footer('城市还没睡','DoodleToday','#a9afcc')]);
 if(c.style==='soft-diary')return root('#786477','#f8edf0',[
  circle(760,480,150,'#f2c9be'),circle(520,-160,750,'#c7d9c8'),
  text('A SOFT NOTE FOR TODAY',21,{letterSpacing:4,color:'#8f778b'}),
  box({marginTop:42,padding:'48px 42px',backgroundColor:'#fff8f7cc',border:'1px solid #d9c5cd',borderRadius:24,flexDirection:'column'},[
   text('此刻的自画像',20,{letterSpacing:3,color:'#a58b9b'}),text(c.title,74,{marginTop:72,maxWidth:820,lineHeight:1.28,whiteSpace:'pre-wrap'}),
   text(c.subtitle,30,{marginTop:42,maxWidth:760,lineHeight:1.7})
  ]),
  box({marginTop:'auto',gap:12,justifyContent:'center',flexWrap:'wrap'},c.tags.map(t=>box({padding:'12px 20px',border:'1px solid #aa91a3',borderRadius:50,backgroundColor:'#fff7f6'},text(t,23)))),
  footer('慢一点，也没关系','DoodleToday','#a58b9b')]);
 if(c.style==='archive')return root('#2f453f','#e9eee7',[
  box({justifyContent:'space-between',alignItems:'center'},[text('PERSONA / INDEX',22,{letterSpacing:4}),text('FILE 001',20,{letterSpacing:3,color:'#d47b5c'})]),
  box({height:2,backgroundColor:'#2f453f',width:'100%',marginTop:18},[]),
  box({marginTop:30,justifyContent:'space-between'},[text('记录日期',18,{color:'#6d817a'}),text('TODAY',18,{letterSpacing:3,color:'#6d817a'})]),
  text(c.title,76,{marginTop:102,maxWidth:850,lineHeight:1.24,whiteSpace:'pre-wrap'}),
  box({marginTop:46,padding:26,border:'1px solid #91a69e',flexDirection:'column'},[text('OBSERVATION',17,{letterSpacing:3,color:'#6d817a'}),text(c.subtitle,30,{marginTop:18,maxWidth:790,lineHeight:1.65})]),
  box({marginTop:'auto',flexDirection:'column'},c.tags.map((t,i)=>box({borderTop:'1px solid #91a69e',padding:'14px 0',justifyContent:'space-between'},[text(`TAG / 0${i+1}`,17,{letterSpacing:2,color:'#d47b5c'}),text(t,26)]))),
  footer('仅作今日观测','DoodleToday','#6d817a')]);
 return root('#f6f0e5','#3e394f',[
  circle(810,740,315,'#d4e49b'),circle(470,955,485,'#3e394f'),circle(925,682,258,'transparent','2px solid #e8eac077'),
  box({justifyContent:'space-between',alignItems:'center'},[text('PERSONA',70,{letterSpacing:-3}),text('VOL. NOW\n仅限今日',20,{textAlign:'right',whiteSpace:'pre-wrap'})]),
  line('#d8d3de'),text('今日人格 · 限时发行',24,{marginTop:26,letterSpacing:4}),
  text(c.title,84,{marginTop:135,maxWidth:630,lineHeight:1.32,whiteSpace:'pre-wrap'}),
  text(c.subtitle,30,{marginTop:42,maxWidth:590,lineHeight:1.7,whiteSpace:'pre-wrap'}),
  box({position:'absolute',bottom:146,left:72,flexDirection:'column',gap:16},c.tags.map((t,i)=>text(`0${i+1} / ${t}`,24,{letterSpacing:2}))),
  footer('不定义你，只记录此刻。','DoodleToday','#e4dfeb')]);
}
function albumCover(c,images){
 const ids=c.pages.flatMap(p=>p.asset_ids).slice(0,2);
 return root('#444d3b','#efe8d8',[
  box({justifyContent:'space-between'},[text('THE LITTLE ARCHIVE',21,{letterSpacing:4}),text('回忆，装订中。',20)]),line('#858e78'),
  text(c.title,78,{marginTop:74,lineHeight:1.3}),text(c.subtitle||'把来过的日子，好好留下。',28,{marginTop:20}),text('封面创作',17,{marginTop:12,color:'#747863'}),
  box({position:'relative',height:690,marginTop:55},ids.map((id,i)=>box({position:'absolute',left:i*340,top:i*65,width:490,height:560,padding:22,backgroundColor:'#fffdf5',transform:`rotate(${i?7:-6}deg)`,boxShadow:'0 9px 25px #4f4a3222',flexDirection:'column'},[
    images[id]?img(images[id],446,455):box({width:446,height:455,backgroundColor:'#d2d3be'},text('MEMORY',42)),
    text(`fragment / 0${i+1}`,20,{marginTop:16,color:'#7b816c'})]))),
  footer('票根回忆册','DoodleToday','#737964')]);
}
function albumPage(c,p,index,images){
 const items=p.asset_ids;
 return root('#41483a','#f3eedf',[
  box({justifyContent:'space-between'},[text(c.title,23),text(`FRAGMENT / ${String(index).padStart(2,'0')}`,20,{letterSpacing:3})]),line('#b2b69f'),
  ...items.map((id,i)=>box({flexDirection:'column',marginTop:items.length===1?58:28},[
    box({padding:18,backgroundColor:'#fffdf7',border:'1px solid #dedacb',transform:`rotate(${i?1:-1}deg)`},[images[id]?img(images[id],900,items.length===1?740:385):text('素材未提供',30)]),
    box({justifyContent:'space-between',marginTop:16,color:'#667055'},[text(c.facts?.[id]?.date||'日期留白',22),text(c.facts?.[id]?.place||'地点留白',22,{maxWidth:650})])
  ])),
  text(p.caption_kind==='excerpt'?'来自你的回忆':'创作旁白',18,{marginTop:30,color:'#8b846f'}),
  text(p.caption||'留一点空白，给下次想起。',30,{marginTop:12,lineHeight:1.55,maxWidth:920}),
  footer('一张票根，一次在场。',`${index+1} / ${c.pages.length+1} · DoodleToday`,'#787e68')]);
}
export async function render(payload){
 const {kind,content:c,images={}}=payload;
 if(!['card','album'].includes(kind)||typeof c?.title!=='string'||!c.title.length||c.title.length>24)throw Error('invalid payload');
 for(const value of Object.values(images))if(typeof value!=='string'||!/^data:image\/(jpeg|png);base64,[A-Za-z0-9+/=]+$/.test(value))throw Error('only embedded raster images allowed');
 const trees=kind==='card'?[card(c)]:[albumCover(c,images),...c.pages.map((p,i)=>albumPage(c,p,i+1,images))];
 if(trees.length>11)throw Error('too many pages');
 const pages=[];
 for(const tree of trees){
  const bounds=[];
  const svg=await satori(tree,{width:1080,height:1440,onNodeDetected:n=>{if(typeof n.props.children==='string')bounds.push(n);},fonts:[{name:'Noto',data:font,weight:400,style:'normal'}]});
  if(bounds.some(n=>n.left<0||n.top<0||n.left+n.width>1081||n.top+n.height>(n.props['data-footer']?1400:1320)))throw Error('text overflow');
  pages.push(new Resvg(svg).render().asPng().toString('base64'));
 }
 return {pages};
}

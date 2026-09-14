// Labelled editorial layout fixtures. These are not model generation results.
import {render} from '../renderer/render.mjs';
import fs from 'node:fs/promises';
import satori from 'satori';
import {Resvg} from '@resvg/resvg-js';
const font=await fs.readFile(new URL('../renderer/fonts/NotoSansSC-Regular.ttf',import.meta.url));
const out=new URL('../frontend/public/samples/',import.meta.url);await fs.mkdir(out,{recursive:true});
for(const style of ['magazine','labels','minimal']){
 const result=await render({kind:'card',content:{title:'低电量\n城市漫游者',subtitle:'出门是为了透气，\n不是为了加入群聊。',tags:['省电模式','随便走走','社交免打扰'],style}});
 await fs.writeFile(new URL(`${style}.png`,out),Buffer.from(result.pages[0],'base64'));
}
const ticket=await satori({type:'div',props:{style:{display:'flex',width:700,height:450,background:'#ded8bc',padding:40,fontFamily:'Noto',color:'#4c5b42',flexDirection:'column',border:'4px solid #677353'},children:[{type:'div',props:{style:{display:'flex',fontSize:24},children:'ADMIT ONE / 排版示例'}},{type:'div',props:{style:{display:'flex',fontSize:65,marginTop:70},children:'周末出走计划'}},{type:'div',props:{style:{display:'flex',fontSize:24,marginTop:70},children:'一张小纸片 · 一段好时光'}}]}},{width:700,height:450,fonts:[{name:'Noto',data:font,weight:400}]});
const img='data:image/png;base64,'+new Resvg(ticket).render().asPng().toString('base64');
const result=await render({kind:'album',content:{title:'周末出走计划',subtitle:'收藏一些，没有赶路的时刻。',pages:[{asset_ids:['a','b'],caption:'把这一天，折进书页里。',caption_kind:'creative'}],facts:{}},images:{a:img,b:img}});
await fs.writeFile(new URL('album.png',out),Buffer.from(result.pages[0],'base64'));
console.log('Created four labelled layout samples.');

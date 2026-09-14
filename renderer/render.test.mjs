import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {render} from './render.mjs';
const content={title:'今日\n普通地开心',subtitle:'没有大事，刚刚好。',tags:['困','想出门','不想社交']};
const cardStyles=['magazine','labels','minimal','receipt','doodle','neon','soft-diary','archive'];
for(const style of cardStyles){
 test(`Chinese PNG / ${style}`,async()=>{
  const result=await render({kind:'card',content:{...content,style}});
  const png=Buffer.from(result.pages[0],'base64');
  assert.equal(png.readUInt32BE(16),1080);assert.equal(png.readUInt32BE(20),1440);
  assert.ok(png.length>20000);
 });
 test(`Maximum Chinese text fits / ${style}`,async()=>{
  await render({kind:'card',content:{title:'文'.repeat(24),subtitle:'字'.repeat(70),tags:['标'.repeat(12),'签'.repeat(12),'签'.repeat(12)],style}});
 });
}
test('Reject unsupported card styles',async()=>{
 await assert.rejects(()=>render({kind:'card',content:{...content,style:'arbitrary-css'}}));
});
test('Reject remote image URLs',async()=>{
 await assert.rejects(()=>render({kind:'album',content:{title:'test',pages:[]},images:{a:'http://169.254.169.254/latest/meta-data'}}));
});
test('Album long caption, two assets and maximum place lengths',async()=>{
 const ids=['a','b'];const raster='data:image/png;base64,'+fs.readFileSync(new URL('../frontend/public/samples/labels.png',import.meta.url)).toString('base64');await render({kind:'album',content:{title:'文'.repeat(24),subtitle:'字'.repeat(70),pages:[{asset_ids:ids,caption:'中'.repeat(90),caption_kind:'creative'}],facts:Object.fromEntries(ids.map(id=>[id,{date:'2026-09-12',place:'地'.repeat(40)}]))},images:{a:raster,b:raster}});
});

import {test} from 'node:test';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import {render} from './render.mjs';
const content={title:'今日\n普通地开心',subtitle:'没有大事，刚刚好。',tags:['困','想出门','不想社交']};
const cardStyles=['magazine','labels','minimal','receipt','doodle','neon','soft-diary','archive'];
// Golden hashes captured before the theme refactor: builtin styles must render byte-identically.
const golden={magazine:'465936ad4be1230bcc84c78be16173e6',labels:'c73996a51e0e771571860321bcf61637',minimal:'f55472a164fdd72d2b0810fcf0ec485a',receipt:'1ae9dfa0024a96db0a876bace53b58ea',doodle:'44c2a32891409ed2641fd2ab35046f27',neon:'0f955df8cb1a9461fcbfbc977e19225a','soft-diary':'6f150ed8822b54fac6fede32fbbfc082',archive:'f2c9ff8c260c6cac16f4c08491b76ead'};
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
test('Builtin styles render byte-identical to golden hashes',async()=>{
 for(const style of cardStyles){
  const result=await render({kind:'card',content:{...content,style}});
  const hash=crypto.createHash('sha256').update(Buffer.from(result.pages[0],'base64')).digest('hex').slice(0,32);
  assert.equal(hash,golden[style],style);
 }
});
const customRecipes={
 editorial:{base_layout:'editorial',palette:['#101820','#f2aa4c','#feeeee'],decoration:['orb'],typography:'display-sans',copy_tone:'测试'},
 'sticker-stack':{base_layout:'sticker-stack',palette:['#fdfdfd','#e63946','#457b9d','#f4a261'],decoration:['label'],typography:'friendly-sans',copy_tone:'测试'},
 'minimal-poster':{base_layout:'minimal-poster',palette:['#faf3dd','#5e503f'],decoration:['rule'],typography:'editorial-serif',copy_tone:'测试'},
 receipt:{base_layout:'receipt',palette:['#fff8e7','#4a3f35','#c1121f'],decoration:['perforation','stamp'],typography:'mono-editorial',copy_tone:'测试'},
 notebook:{base_layout:'notebook',palette:['#fefae0','#606c38','#dda15e','#bc6c25'],decoration:['tape','note'],typography:'friendly-sans',copy_tone:'测试'},
 'night-grid':{base_layout:'night-grid',palette:['#0b0b1e','#ff9ad5','#7bf1a8','#ffffff'],decoration:['neon-orb','grid'],typography:'display-sans',copy_tone:'测试'},
 'soft-diary':{base_layout:'soft-diary',palette:['#fff1e6','#9d8189','#f4acb7'],decoration:['soft-orb','frame'],typography:'editorial-serif',copy_tone:'测试'},
 'archive-grid':{base_layout:'archive-grid',palette:['#edf2f4','#2b2d42','#8d99ae','#ef233c'],decoration:['grid','index','data-block'],typography:'mono-editorial',copy_tone:'测试'}};
for(const [layout,recipe] of Object.entries(customRecipes)){
 test(`Custom theme renders / ${layout}`,async()=>{
  const result=await render({kind:'card',content:{...content,style:'u_deadbeef',style_snapshot:{id:'u_deadbeef',name:'自定义·测试',registry_version:1,recipe}}});
  const png=Buffer.from(result.pages[0],'base64');
  assert.equal(png.readUInt32BE(16),1080);assert.equal(png.readUInt32BE(20),1440);assert.ok(png.length>20000);
 });
}
test('Reject custom snapshot with unknown base layout',async()=>{
 const recipe={...customRecipes['night-grid'],base_layout:'arbitrary-css'};
 await assert.rejects(()=>render({kind:'card',content:{...content,style:'u_deadbeef',style_snapshot:{id:'u_deadbeef',name:'x',registry_version:1,recipe}}}));
});
test('Reject custom snapshot with decoration outside layout whitelist',async()=>{
 const recipe={...customRecipes['night-grid'],decoration:['orb']};
 await assert.rejects(()=>render({kind:'card',content:{...content,style:'u_deadbeef',style_snapshot:{id:'u_deadbeef',name:'x',registry_version:1,recipe}}}));
});
test('Reject custom snapshot with non-hex palette',async()=>{
 const recipe={...customRecipes['night-grid'],palette:['red','blue']};
 await assert.rejects(()=>render({kind:'card',content:{...content,style:'u_deadbeef',style_snapshot:{id:'u_deadbeef',name:'x',registry_version:1,recipe}}}));
});
test('Reject remote image URLs',async()=>{
 await assert.rejects(()=>render({kind:'album',content:{title:'test',pages:[]},images:{a:'http://169.254.169.254/latest/meta-data'}}));
});
test('Album long caption, two assets and maximum place lengths',async()=>{
 const ids=['a','b'];const raster='data:image/png;base64,'+fs.readFileSync(new URL('../frontend/public/samples/labels.png',import.meta.url)).toString('base64');await render({kind:'album',content:{title:'文'.repeat(24),subtitle:'字'.repeat(70),pages:[{asset_ids:ids,caption:'中'.repeat(90),caption_kind:'creative'}],facts:Object.fromEntries(ids.map(id=>[id,{date:'2026-09-12',place:'地'.repeat(40)}]))},images:{a:raster,b:raster}});
});

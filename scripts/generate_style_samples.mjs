import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {render} from '../renderer/render.mjs';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const output=path.join(root,'frontend','public','samples');
const content={title:'低电量\n城市漫游者',subtitle:'今天只想把行程调成省电模式。',tags:['想躺平','有点期待','不想社交']};
for(const style of ['receipt','doodle','neon','soft-diary','archive']){
 const result=await render({kind:'card',content:{...content,style}});
 fs.writeFileSync(path.join(output,`${style}.png`),Buffer.from(result.pages[0],'base64'));
}

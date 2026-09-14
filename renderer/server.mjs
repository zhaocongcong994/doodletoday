import http from 'node:http';
import { timingSafeEqual } from 'node:crypto';
import fs from 'node:fs';
import dotenv from 'dotenv';
import { render } from './render.mjs';
dotenv.config({path:new URL('../.env',import.meta.url),quiet:true});
const config=JSON.parse(fs.readFileSync(new URL('../app.json',import.meta.url)));
const token=process.env.RENDER_TOKEN;
if(!token)throw Error('RENDER_TOKEN is required. Run scripts/setup.py.');
let busy=false;
http.createServer(async(req,res)=>{
 const reply=(status,obj)=>{res.writeHead(status,{'Content-Type':'application/json'});res.end(JSON.stringify(obj));};
 if(req.url==='/health'&&req.method==='GET')return reply(200,{ready:true});
 const supplied=Buffer.from(req.headers['x-render-token']||'');const expected=Buffer.from(token);
 if(supplied.length!==expected.length||!timingSafeEqual(supplied,expected))return reply(403,{error:'unauthorized'});
 if(req.url!=='/render'||req.method!=='POST')return reply(404,{error:'not_found'});
 if(busy)return reply(503,{error:'busy'});
 let size=0;const chunks=[];
 try{
  for await(const chunk of req){size+=chunk.length;if(size>50_000_000){reply(413,{error:'too_large'});req.destroy();return;}chunks.push(chunk);}
  busy=true;
  reply(200,await render(JSON.parse(Buffer.concat(chunks).toString())));
 }catch{reply(422,{error:'render_failed'});}finally{busy=false;}
}).listen(Number(process.env.RENDER_PORT||config.render_port),process.env.RENDER_HOST||'127.0.0.1',()=>console.log(`Renderer ready on ${process.env.RENDER_PORT||config.render_port}`));

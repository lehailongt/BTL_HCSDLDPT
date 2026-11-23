// Component event-contract test; no browser or network required.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('ui_components/organ_mask_editor/index.html','utf8');
const script=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const listeners={},messages=[];
const ctx=new Proxy({}, {get:(obj,key)=>obj[key]||(()=>{}),set:(obj,key,value)=>(obj[key]=value,true)});
const nodes={};
for(const id of ['canvas','organ','finish','undo','clear','message'])nodes[id]={value:'stem'};
Object.assign(nodes.canvas,{width:256,height:256,getContext:()=>ctx,
  getBoundingClientRect:()=>({left:0,top:0,width:512,height:512}),
  addEventListener:(event,handler)=>listeners[event]=handler});
class Picture {set src(value){this.complete=true;this.onload?.();}}
const context={document:{body:{scrollHeight:600},getElementById:id=>nodes[id]},
  parent:{postMessage:message=>messages.push(message)},Image:Picture,
  window:{addEventListener:(event,handler)=>listeners[event]=handler}};
vm.runInNewContext(script,context);
assert(messages.some(m=>m.type==='streamlit:componentReady'));
listeners.message({data:{type:'streamlit:render',args:{token:'a',width:256,height:256,image:'data:image/png;base64,',polygons:{stem:[],calyx:[]}}}});
for(const [clientX,clientY] of [[20,20],[40,20],[30,80]])listeners.pointerdown({clientX,clientY});
nodes.finish.onclick();
const values=messages.filter(m=>m.type==='streamlit:setComponentValue');
assert.equal(values.length,1);assert.equal(values[0].dataType,'json');
assert.equal(JSON.stringify(values[0].value.polygons.stem[0]),'[[10,10],[20,10],[15,40]]');
nodes.clear.onclick();
assert.equal(messages.filter(m=>m.type==='streamlit:setComponentValue').at(-1).value.polygons.stem.length,0);
console.log('PASS: ready, render, scaled coordinates, close polygon, clear, JSON payload');

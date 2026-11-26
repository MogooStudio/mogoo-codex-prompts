'use strict';
const $ = id => document.getElementById(id);
const pending = new Map();
let sequence = 0, initialized = false, threadId = null, hostTheme = null, canDraft = false;
let state = null, category = '全部', editing = null, editingRevision = 0;
let categorySource = null, categoryRevision = 0, writeBusy = false;
let theme = 'auto', titleDraft = '', captureCategory = null;
const media = matchMedia('(prefers-color-scheme: dark)');

function message(text, retry = false) {
  $('notice').textContent = text;
  $('retry').hidden = !retry;
}
function request(method, params) {
  if (parent === window) return Promise.reject(Error('请从 Codex 聊天打开常用提示词。'));
  const id = 'prompt-' + (++sequence);
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => { pending.delete(id); reject(Error('宿主响应超时。')); }, 10000);
    pending.set(id, {resolve, reject, timer});
    parent.postMessage({jsonrpc:'2.0', id, method, params}, '*');
  });
}
function applyTheme() {
  document.documentElement.dataset.theme = theme === 'auto' ? hostTheme || (media.matches ? 'dark' : 'light') : theme;
}
function hostContext(context) {
  if (['light','dark'].includes(context?.theme)) hostTheme = context.theme;
  applyTheme();
}
window.addEventListener('message', event => {
  const m = event.data;
  if (event.source !== parent || m?.jsonrpc !== '2.0') return;
  const ticket = pending.get(m.id);
  if (ticket && !m.method) {
    clearTimeout(ticket.timer); pending.delete(m.id);
    if (m.error) ticket.reject(Error(m.error.message)); else ticket.resolve(m.result);
  } else if (m.method === 'ui/notifications/tool-result' && m.params?.structuredContent &&
             Object.hasOwn(m.params.structuredContent,'threadId')) {
    const owner=m.params.structuredContent.threadId || null;
    if(threadId!==owner)insertionEpoch++;
    threadId=owner;
    if (state) readyMessage();
  } else if (m.method === 'ui/notifications/host-context-changed') {
    hostContext(m.params);
  } else if (m.method === 'ui/resource-teardown') {
    threadId = null; initialized = false;
    if (m.id != null) parent.postMessage({jsonrpc:'2.0',id:m.id,result:{}},'*');
  }
});
media.addEventListener('change',applyTheme);
applyTheme();
function readyMessage(){
  message(threadId && canDraft ? '点击提示词，追加到当前聊天草稿。' : '当前聊天未提供草稿入口，可复制提示词。');
  render();
}
let readTicket = 0;
async function dataCall(action, data = {}) {
  const result = await request('tools/call', {name:'prompts_collection',arguments:{action,data}});
  if (result?.isError || !Array.isArray(result?.structuredContent?.prompts))
    throw Error(result?.content?.[0]?.text || '读取收藏失败。');
  return result.structuredContent;
}
function adopt(next) {
  state=next;
  theme=state.appearance;
  applyTheme();
  if (!state.categories.includes(category)) category='全部';
  render();
}
async function reload() {
  const ticket=++readTicket;
  try {
    const data=await dataCall('list');
    if (ticket===readTicket && !writeBusy) adopt(data);
  } catch(error) { message(error.message,true); }
}
async function change(action,data,revision=state?.revision) {
  if (writeBusy) throw Error('正在保存，请稍后重试。');
  writeBusy=true;
  ++readTicket;
  try { adopt(await dataCall(action,{...data,revision})); }
  finally { writeBusy=false; }
}
function inlineError(dialog, error) {
  let line=dialog.querySelector('.inline-error');
  if (!line) { line=el('p','inline-error'); line.setAttribute('role','alert'); dialog.prepend(line); }
  line.textContent=error.message;
}
function clearError(dialog) {dialog.querySelector('.inline-error')?.remove();}
function el(tag,cls,text) {
  const node=document.createElement(tag);
  if(cls)node.className=cls;
  if(text!=null)node.textContent=text;
  return node;
}
function button(label,act,cls='text-action'){
  const node=el('button',cls,label);node.type='button';node.onclick=act;return node;
}
function available(){return initialized && canDraft && !!threadId;}
let insertionQueue=Promise.resolve(), insertionEpoch=0;
function insert(p) {
  if(document.hidden)return;
  const owner=threadId, epoch=insertionEpoch, draft=available();
  insertionQueue=insertionQueue.then(async()=>{
    if(document.hidden || owner!==threadId || epoch!==insertionEpoch || draft!==available())return;
    await insertOne(p);
  }).catch(error=>{insertionEpoch++;message(error.message);});
}
async function insertOne(p) {
  if(!available()){
    try{await navigator.clipboard.writeText(p.body);message('已复制，可粘贴到草稿。');}
    catch{message('复制未成功，可展开正文手动选择。');}
    return;
  }
  try {
    const result=await request('ui/message',{role:'user',content:[{type:'text',text:p.body}],
        _meta:{'openai/message':{target:'active',send:false}}});
    if(result?.isError)throw Error('宿主拒绝了填入请求。');
  } catch(error){
    insertionEpoch++;message(error.message+' 请检查当前草稿后再试。');return;
  }
  try{await change('use',{id:p.id});message('已填入当前聊天草稿。');}
  catch{message('已填入草稿。最近使用记录更新失败。',true);}
}
function makeRow(p,fromHistory=false) {
  const item=el('div','item'),row=button('',()=>{
    if(fromHistory)$('recent-dialog').close();
    insert(p);
  },'row');
  const title=el('span','entry-title'),verb=available()?'填入':'复制';
  title.append(el('span','name',p.title),el('span','insert',verb));
  row.setAttribute('aria-label',verb+'：'+p.title);
  const body=p.body.trim(),prefix=body.split(/\r?\n/).slice(0,2).join('\n').slice(0,64);
  const preview=el('span','excerpt',prefix+(body!==prefix?'…':''));
  row.append(el('span','meta',p.category),title,preview);
  const actions=el('div','row-actions');
  if(body!==prefix){
    const full=el('pre','full-body',p.body);full.hidden=true;
    const toggle=button('查看全文',()=>{
      full.hidden=!full.hidden;preview.hidden=!full.hidden;
      toggle.textContent=full.hidden?'查看全文':'收起全文';toggle.setAttribute('aria-expanded',String(!full.hidden));
    });
    toggle.setAttribute('aria-expanded','false');actions.append(toggle);item.append(row,full);
  }else item.append(row);
  if(!fromHistory){
    const more=button('•••',()=>itemMenu(p),'item-menu');more.setAttribute('aria-label',p.title+'的操作');actions.append(more);
  }
  item.append(actions);return item;
}
function render() {
  if(!state)return;
  const nav=document.querySelector('.filters'),list=$('list');
  nav.replaceChildren();list.replaceChildren();
  for(const name of ['全部',...state.categories]){
    const tab=button(name,()=>{category=name;render();},'tab');tab.setAttribute('aria-pressed',String(name===category));nav.append(tab);
  }
  const q=$('query').value.trim().toLowerCase();
  const found=state.prompts.filter(p=>(category==='全部'||p.category===category)&&
     (q?(p.title+' '+p.body).toLowerCase().includes(q):category!=='全部'||p.saved));
  const title=el('h2','section-title',q?'搜索结果':category==='全部'?'我的收藏':category);
  title.append(el('span','count',found.length));list.append(title,...found.map(p=>makeRow(p)));
  if(!found.length)list.append(el('p','empty',q?'没有找到匹配的提示词。':'这里还没有提示词。'),
      button(q?'清除搜索':'收藏一条',()=>{if(q){$('query').value='';render();$('query').focus();}else openCapture();}));
}
function itemMenu(p){
  const dialog=$('item-menu');clearError(dialog);$('item-name').textContent=p.title;
  const revision=state.revision;
  $('item-options').replaceChildren(button('编辑或更改分类',()=>{dialog.close();openCapture(p);}),
    button('复制为新提示词',()=>{dialog.close();openCapture(p,true);}),
    button(p.saved?'移出我的收藏':'加入我的收藏',async()=>{
      try{await change('favorite',{id:p.id},revision);dialog.close();message('已更新收藏。');}
      catch(e){inlineError(dialog,e);await reload();}
    }));
  dialog.showModal();
}
function options(selected){
  const select=$('capture-category');select.replaceChildren(...state.categories.map(c=>new Option(c,c)));
  select.value=state.categories.includes(selected)?selected:state.categories[0];
}
function openCapture(p=null,copy=false){
  if(!state)return;
  editing=p&&!copy?p.id:null;editingRevision=state.revision;
  const form=$('capture-form');clearError($('capture'));
  $('capture-title').textContent=editing?'编辑提示词':copy?'复制提示词':'快速收藏';
  form.querySelector('.primary').textContent=editing?'保存':'收藏';
  form.elements.title.value=p?p.title:titleDraft;
  $('capture-body').value=p?p.body:bodyDraft;
  $('capture-body').setCustomValidity('');
  options(p?p.category:captureCategory||category);$('capture').showModal();
}
let bodyDraft='';
$('capture').onclose=()=>{
  if(!editing){bodyDraft=$('capture-body').value;titleDraft=$('capture-form').elements.title.value;captureCategory=$('capture-category').value;}
};
$('cancel').onclick=()=>$('capture').close();
$('capture-body').oninput=()=>$('capture-body').setCustomValidity('');
$('capture-form').onsubmit=async e=>{
  e.preventDefault();if(writeBusy)return;
  const form=e.target,body=form.elements.body.value;
  if(!body.trim()){form.elements.body.setCustomValidity('请输入正文。');form.elements.body.reportValidity();return;}
  try{
    await change(editing?'edit':'create',{id:editing,body,title:form.elements.title.value.trim()||body.trim().split(/\r?\n/)[0],category:form.elements.category.value},editingRevision);
    category=form.elements.category.value;$('query').value='';form.reset();$('capture').close();render();message('已保存到本机。');
  }catch(err){inlineError($('capture'),err);await reload();if(!editing)editingRevision=state.revision;}
};
function categoryDialog(old=null){
  categorySource=old;categoryRevision=state.revision;
  $('cat-title').textContent=old?'重命名分类':'新建分类';
  $('category-form').querySelector('.primary').textContent=old?'保存':'创建分类';
  $('cat-name').value=old||'';$('cat-error').hidden=true;$('category-dialog').showModal();
}
function manageRows(){
  const box=$('category-list');box.replaceChildren();
  state.categories.forEach((c,i)=>{
    const row=el('div','manage-row');row.append(el('span','',c),button('改名',()=>categoryDialog(c)));
    for(const step of [-1,1]){
      const b=button(step<0?'↑':'↓',async()=>{
        try{await change('move_category',{category:c,step});manageRows();}
        catch(err){inlineError($('manage'),err);await reload();manageRows();}
      });
      b.disabled=i+step<0||i+step>=state.categories.length;
      b.setAttribute('aria-label',(step<0?'上移':'下移')+c);row.append(b);
    }
    box.append(row);
  });
}
$('add-category').onclick=()=>{if(state){clearError($('manage'));manageRows();$('manage').showModal();}};
$('manage-add').onclick=() => categoryDialog();
$('capture-add-category').onclick=()=>categoryDialog();
$('cat-cancel').onclick=()=>$('category-dialog').close();
$('category-form').onsubmit=async e=>{
  e.preventDefault();const name=$('cat-name').value.trim();
  try{
    await change(categorySource?'rename_category':'add_category',{name,category:categorySource},categoryRevision);
    $('category-dialog').close();
    if($('capture').open){options(name);editingRevision=state.revision;}
    if($('manage').open)manageRows();
  }catch(err){$('cat-error').textContent=err.message;$('cat-error').hidden=false;await reload();categoryRevision=state.revision;}
};
$('appearance-open').onclick=()=>{
  if(!state)return;
  const dialog=$('appearance-dialog');clearError(dialog);
  const input=dialog.querySelector('input[value="'+theme+'"]');input.checked=true;dialog.showModal();input.focus();
};
$('appearance-dialog').onchange=async e=>{
  try{await change('appearance',{mode:e.target.value});}
  catch(err){inlineError($('appearance-dialog'),err);$('appearance-dialog').querySelector('input[value="'+theme+'"]').checked=true;}
};
$('new').onclick=()=>openCapture();
$('recent-trigger').onclick=()=>{
  if(!state)return;
  const items=$('recent-items');items.replaceChildren();
  for(const id of state.recent){const p=state.prompts.find(x=>x.id===id);if(p)items.append(makeRow(p,true));}
  if(!items.children.length)items.append(el('p','empty','填入过的提示词会出现在这里。'));
  $('recent-dialog').showModal();
};
$('query').oninput=render;
document.addEventListener('keydown',e=>{
  if(e.key==='/'&&!e.ctrlKey&&!e.metaKey&&!document.querySelector('dialog[open]')&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)){e.preventDefault();$('query').focus();}
});
document.addEventListener('visibilitychange',()=>{if(initialized&&!document.hidden&&!document.querySelector('dialog[open]'))reload();});
window.addEventListener('focus',()=>{if(initialized&&!document.querySelector('dialog[open]'))reload();});
async function start(){
  try {
    if(!initialized){
      const info=await request('ui/initialize',{protocolVersion:'2026-01-26',appInfo:{name:'mogoo-codex-prompts',version:'0.1.4'},appCapabilities:{}});
      canDraft=!!info?.hostCapabilities?.experimental?.['openai/message'];hostContext(info?.hostContext);
      initialized=true;parent.postMessage({jsonrpc:'2.0',method:'ui/notifications/initialized'},'*');
    }
    await reload();
    if(state)readyMessage();
  }catch(e){message(e.message,true);}
}
$('retry').onclick=start;
start();

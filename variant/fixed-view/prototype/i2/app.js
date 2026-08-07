import { loadI2Data } from "./data-loader.js";
import { moduleSvg, renderScene } from "./renderer.js";

const OPENING_LABELS={
  "two-hole-handle":"Alça de dois furos",
  "one-hole-point":"Ponto de um furo",
  "pass-through":"Abertura passante"
};
const COLORS=[
  {id:"gianduia",name:"Cinza Gianduia",value:"#918981"},
  {id:"graphite",name:"Grafite",value:"#292b2c"},
  {id:"black",name:"Preto",value:"#111214"},
  {id:"sand",name:"Areia",value:"#b7a88f"},
  {id:"sage",name:"Sálvia",value:"#829180"},
  {id:"petroleum",name:"Azul petróleo",value:"#244e55"},
  {id:"white",name:"Branco",value:"#e9e7e1"}
];
const STORAGE_KEY="mobilipresenter.fixed-view.i2";
const assets=window.MOBILI_I1_ASSETS;
if(!assets) throw new Error("Assets base não carregados.");

const data=await loadI2Data();
const {moduleById,orderedModules}=data;
const placementById=new Map(data.layout.placements.map(item=>[item.moduleId,item]));

const el={
  moduleList:document.querySelector("#module-list"),
  rowTemplate:document.querySelector("#module-row-template"),
  selectionCount:document.querySelector("#selection-count"),
  catalogList:document.querySelector("#catalog-list-view"),
  catalogDetail:document.querySelector("#catalog-detail-view"),
  moduleDetail:document.querySelector("#module-detail"),
  backToList:document.querySelector("#back-to-list"),
  sceneWrap:document.querySelector("#scene-wrap"),
  sceneModules:document.querySelector("#scene-modules"),
  sceneHitAreas:document.querySelector("#scene-hit-areas"),
  sceneEmpty:document.querySelector("#scene-empty-state"),
  projectImage:document.querySelector("#project-image"),
  colorOptions:document.querySelector("#color-options"),
  selectedModuleConfig:document.querySelector("#selected-module-config"),
  selectedModuleName:document.querySelector("#selected-module-name"),
  openingSelect:document.querySelector("#opening-select"),
  openingRecommendation:document.querySelector("#opening-recommendation"),
  commercialCount:document.querySelector("#commercial-count"),
  modifierCount:document.querySelector("#modifier-count"),
  issuesList:document.querySelector("#issues-list"),
  diagnosticsSummary:document.querySelector("#diagnostics-summary"),
  finalizeButton:document.querySelector("#finalize-button"),
  enableAll:document.querySelector("#enable-all"),
  resetAll:document.querySelector("#reset-all"),
  applyRecommended:document.querySelector("#apply-recommended")
};

function recommendedOpening(module){return module.recommendedOpeningOptions?.[0]??null;}
function defaultState(){
  return {
    enabled:[],
    selectedId:null,
    lastEnabledId:null,
    colorId:"gianduia",
    baseMode:"neutral-wall",
    openings:Object.fromEntries(orderedModules.filter(m=>m.openingOptions.length).map(m=>[m.id,recommendedOpening(m)]))
  };
}
function loadState(){
  const fallback=defaultState();
  try{
    const raw=localStorage.getItem(STORAGE_KEY);
    if(!raw)return fallback;
    const parsed=JSON.parse(raw),valid=new Set(orderedModules.map(m=>m.id));
    return {...fallback,...parsed,
      enabled:Array.isArray(parsed.enabled)?parsed.enabled.filter(id=>valid.has(id)):[],
      selectedId:valid.has(parsed.selectedId)?parsed.selectedId:null,
      lastEnabledId:valid.has(parsed.lastEnabledId)?parsed.lastEnabledId:null,
      openings:{...fallback.openings,...(parsed.openings||{})}
    };
  }catch(error){console.warn("Estado local inválido; baseline I2 restaurada.",error);return fallback;}
}
let state=loadState();
let transientMessage="";
const isEnabled=id=>state.enabled.includes(id);
const selectedColor=()=>COLORS.find(c=>c.id===state.colorId)??COLORS[0];

function save(){localStorage.setItem(STORAGE_KEY,JSON.stringify(state));}
function commit(){save();render();}

function setEnabled(id,enabled,{select=false}={}){
  const next=new Set(state.enabled);
  if(enabled){next.add(id);state.lastEnabledId=id;}
  else{next.delete(id);if(state.selectedId===id)state.selectedId=null;}
  state.enabled=orderedModules.map(m=>m.id).filter(id=>next.has(id));
  if(select)state.selectedId=id;
  transientMessage="";
  commit();
}
function selectModule(id,{showDetail=true}={}){
  if(!moduleById.has(id))return;
  state.selectedId=id;
  if(showDetail){el.catalogList.hidden=true;el.catalogDetail.hidden=false;}
  transientMessage="";
  commit();
}

function currentIssues(){
  const out=[];
  if(isEnabled("lighting")&&!isEnabled("refrigerator-side-panel")){
    out.push({id:"lighting-requires-refrigerator-side-panel",moduleId:"lighting",severity:"blocking",
      message:"A iluminação requer a lateral da geladeira (item 04).",resolutionLabel:"Incluir item 04",
      resolve:()=>setEnabled("refrigerator-side-panel",true)});
  }
  for(const module of orderedModules){
    if(!isEnabled(module.id)||!module.openingOptions.length)continue;
    const current=state.openings[module.id];
    if(!module.recommendedOpeningOptions.includes(current)){
      out.push({id:`opening-${module.id}`,moduleId:module.id,severity:"warning",
        message:`${module.name}: ${OPENING_LABELS[current]||"opção atual"} diverge do preset recomendado.`,
        resolutionLabel:"Usar recomendado",resolve:()=>{state.openings[module.id]=recommendedOpening(module);commit();}});
    }
  }
  return out;
}

function renderModuleList(issues){
  const issueByModule=new Map(issues.filter(i=>i.moduleId).map(i=>[i.moduleId,i]));
  el.moduleList.replaceChildren();
  for(const module of orderedModules){
    const fragment=el.rowTemplate.content.cloneNode(true);
    const row=fragment.querySelector(".module-row");
    const checkbox=fragment.querySelector("input");
    const openButton=fragment.querySelector(".module-open");
    const thumb=fragment.querySelector(".module-thumb");
    const badge=fragment.querySelector(".module-badge");
    const enabled=isEnabled(module.id),issue=issueByModule.get(module.id);
    row.dataset.moduleId=module.id;
    row.classList.toggle("is-enabled",enabled);
    row.classList.toggle("has-issue",Boolean(issue));
    checkbox.checked=enabled;
    checkbox.setAttribute("aria-label",`${enabled?"Remover":"Incluir"} ${module.name}`);
    checkbox.addEventListener("change",()=>setEnabled(module.id,checkbox.checked));
    openButton.setAttribute("aria-label",`Detalhar ${module.name}`);
    openButton.addEventListener("click",()=>selectModule(module.id));
    thumb.innerHTML=moduleSvg(module,{color:selectedColor().value,opening:state.openings[module.id]});
    fragment.querySelector(".module-number").textContent=`ITEM ${module.catalogNumber}`;
    fragment.querySelector(".module-name").textContent=module.name;
    fragment.querySelector(".module-status").textContent=enabled?"Incluído na composição":"Disponível";
    if(issue){badge.hidden=false;badge.title=issue.message;}
    el.moduleList.append(fragment);
  }
  el.selectionCount.textContent=`${state.enabled.length}/8`;
}

function dimensionsText(module){
  const d=module.dimensionsMm;
  if(!d)return"Dimensões ainda não confirmadas.";
  if(Number.isFinite(d.width)&&Number.isFinite(d.height)&&Number.isFinite(d.depth))return`${d.width} × ${d.height} × ${d.depth} mm`;
  if(Number.isFinite(d.height)&&Number.isFinite(d.depth)&&Number.isFinite(d.thickness))return`${d.height} × ${d.depth} × ${d.thickness} mm (A × P × E)`;
  return"Dimensões parciais.";
}
function structuralSummary(module){
  const s=module.structuralFeatures||{},parts=[];
  if(s.drawers)parts.push(`${s.drawers} gaveta${s.drawers===1?"":"s"}`);
  if(s.doors)parts.push(`${s.doors} porta${s.doors===1?"":"s"}`);
  if(s.flapDoors)parts.push(`${s.flapDoors} porta basculante`);
  if(s.fixedShelves)parts.push(`${s.fixedShelves} prateleira fixa`);
  if(s.niches)parts.push(`${s.niches} nicho`);
  return parts.length?parts.join(" · "):"Sem divisão frontal aplicável.";
}
function renderDetail(){
  const module=moduleById.get(state.selectedId);
  if(!module){el.catalogList.hidden=false;el.catalogDetail.hidden=true;el.moduleDetail.replaceChildren();return;}
  const materials=module.detail.materials?.length?module.detail.materials.map(i=>`<li>${i.label}: ${i.value||"não informado"}</li>`).join(""):"<li>Materiais ainda não consolidados.</li>";
  const hardware=module.detail.hardware?.length?module.detail.hardware.map(i=>`<li>${i.label}</li>`).join(""):"<li>Ferragens ainda não consolidadas.</li>";
  const notes=module.detail.notes?.length?module.detail.notes.map(n=>`<li>${n}</li>`).join(""):"<li>Sem observações adicionais registradas.</li>";
  el.moduleDetail.innerHTML=`
    <p class="eyebrow">ITEM ${module.catalogNumber}</p>
    <h2>${module.name}</h2>
    <div class="detail-hero">${moduleSvg(module,{detail:true,color:selectedColor().value,opening:state.openings[module.id]})}</div>
    <div class="detail-meta">
      <section class="detail-block"><h3>Descrição</h3><p class="field-note">${module.detail.description||"Descrição ainda não consolidada."}</p></section>
      <section class="detail-block"><h3>Dimensões</h3><p class="field-note">${dimensionsText(module)}</p></section>
      <section class="detail-block"><h3>Estrutura</h3><p class="field-note">${structuralSummary(module)}</p></section>
      <section class="detail-block"><h3>Materiais</h3><ul class="detail-list">${materials}</ul></section>
      <section class="detail-block"><h3>Ferragens</h3><ul class="detail-list">${hardware}</ul></section>
      <section class="detail-block"><h3>Observações</h3><ul class="detail-list">${notes}</ul></section>
    </div>`;
}
function renderColors(){
  el.colorOptions.replaceChildren();
  for(const color of COLORS){
    const button=document.createElement("button");
    button.type="button";button.className="swatch";button.classList.toggle("is-active",color.id===state.colorId);
    button.style.setProperty("--swatch",color.value);button.title=color.name;
    button.setAttribute("aria-label",`Cor ${color.name}`);button.setAttribute("aria-pressed",String(color.id===state.colorId));
    button.addEventListener("click",()=>{state.colorId=color.id;transientMessage=`Frentes e acabamentos visíveis alterados para ${color.name}.`;commit();});
    el.colorOptions.append(button);
  }
}
function renderSelectedConfig(){
  const module=moduleById.get(state.selectedId),configurable=Boolean(module?.openingOptions.length);
  el.selectedModuleConfig.disabled=!configurable;
  el.selectedModuleName.textContent=module?module.name:"Selecione um módulo";
  el.openingSelect.replaceChildren();
  if(!configurable){el.openingRecommendation.textContent=module?"Este item não possui abertura configurável.":"";return;}
  for(const option of module.openingOptions){
    const item=document.createElement("option");item.value=option;item.textContent=OPENING_LABELS[option]||option;item.selected=state.openings[module.id]===option;el.openingSelect.append(item);
  }
  el.openingRecommendation.textContent=`Recomendado: ${module.recommendedOpeningOptions.map(o=>OPENING_LABELS[o]).join(" ou ")}.`;
}
function renderIssues(issues){
  el.issuesList.replaceChildren();
  for(const issue of issues){
    const card=document.createElement("article");card.className=`issue-card ${issue.severity}`;
    const label=document.createElement("strong");label.textContent=issue.severity==="blocking"?"Ação necessária":"Recomendação";
    const msg=document.createElement("span");msg.textContent=issue.message;
    const action=document.createElement("button");action.type="button";action.textContent=issue.resolutionLabel;action.addEventListener("click",issue.resolve);
    card.append(label,msg,action);el.issuesList.append(card);
  }
  const blocking=issues.filter(i=>i.severity==="blocking");
  el.diagnosticsSummary.classList.toggle("has-blocking",blocking.length>0);
  el.diagnosticsSummary.textContent=transientMessage||(blocking.length?`${blocking.length} bloqueio impede a revisão.`:issues.length?`${issues.length} recomendação disponível.`:state.enabled.length?"Composição pronta para revisão.":"Nenhum módulo incluído; fogão convencional é o fallback do item 02.");
  el.finalizeButton.disabled=blocking.length>0||state.enabled.length===0;
}
function renderCommercial(issues){
  el.commercialCount.textContent=String(state.enabled.length);
  const modified=orderedModules.filter(m=>isEnabled(m.id)&&m.openingOptions.length&&!m.recommendedOpeningOptions.includes(state.openings[m.id])).length;
  el.modifierCount.textContent=modified?`${modified} override${modified===1?"":"s"} de abertura`:"Nenhum override de abertura";
  renderIssues(issues);
}
function renderBaseMode(){
  el.sceneWrap.dataset.baseMode=state.baseMode;
  document.querySelectorAll("[data-base-mode]").forEach(button=>{
    if(!(button instanceof HTMLButtonElement))return;
    const active=button.dataset.baseMode===state.baseMode;button.classList.toggle("is-active",active);button.setAttribute("aria-pressed",String(active));
  });
  document.querySelector(".reference-context").src=assets.referenceComposition;
  el.projectImage.src=assets.projectImage;
}
function render(){
  const issues=currentIssues();
  renderModuleList(issues);
  renderScene({sceneModules:el.sceneModules,sceneHitAreas:el.sceneHitAreas,sceneEmpty:el.sceneEmpty,orderedModules,placementById,
    enabledIds:state.enabled,selectedId:state.selectedId,lastEnabledId:state.lastEnabledId,color:selectedColor().value,layout:data.layout,onSelect:selectModule});
  renderDetail();renderColors();renderSelectedConfig();renderCommercial(issues);renderBaseMode();
}

el.backToList.addEventListener("click",()=>{el.catalogList.hidden=false;el.catalogDetail.hidden=true;transientMessage="";render();});
el.openingSelect.addEventListener("change",()=>{if(!state.selectedId)return;state.openings[state.selectedId]=el.openingSelect.value;transientMessage="Abertura atualizada; o cliente pode manter o override.";commit();});
el.applyRecommended.addEventListener("click",()=>{for(const m of orderedModules)if(m.openingOptions.length)state.openings[m.id]=recommendedOpening(m);transientMessage="Preset recomendado aplicado.";commit();});
el.enableAll.addEventListener("click",()=>{state.enabled=orderedModules.map(m=>m.id);state.lastEnabledId=orderedModules.at(-1)?.id??null;transientMessage="Conjunto completo ativado.";commit();});
el.resetAll.addEventListener("click",()=>{state=defaultState();el.catalogList.hidden=false;el.catalogDetail.hidden=true;transientMessage="Seleção limpa; fogão convencional permanece como fallback do item 02.";commit();});
el.finalizeButton.addEventListener("click",()=>{const blocking=currentIssues().filter(i=>i.severity==="blocking");if(blocking.length||!state.enabled.length)return;transientMessage=`Revisão liberada para ${state.enabled.length} módulo${state.enabled.length===1?"":"s"}.`;render();});
document.querySelectorAll("[data-base-mode]").forEach(button=>button.addEventListener("click",()=>{state.baseMode=button.dataset.baseMode;transientMessage=state.baseMode==="reference-context"?"Contexto de referência ativado como guia visual.":"Parede neutra ativada.";commit();}));

render();

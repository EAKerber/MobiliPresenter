const SVG_NS = "http://www.w3.org/2000/svg";

function svg(name, attrs = {}) {
  const node = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
  return node;
}

function finishColor(module, color) {
  return module.visibleFinish?.presetControlled ? color : "#f3f1ec";
}

function openingDecoration(module, element, opening, x, y, w, h, detail) {
  if (!["door", "drawer", "flap-door", "panel"].includes(element.type)) return "";
  const sw = detail ? 7 : 2.5;
  if (opening === "two-hole-handle") {
    const horizontal = element.type === "drawer" || element.type === "flap-door";
    return horizontal
      ? `<path d="M${x+w*.38} ${y+h*.76}H${x+w*.62}" stroke="#c7b28b" stroke-width="${sw}" stroke-linecap="round"/>`
      : `<path d="M${x+w*.82} ${y+h*.36}V${y+h*.64}" stroke="#c7b28b" stroke-width="${sw}" stroke-linecap="round"/>`;
  }
  if (opening === "one-hole-point") {
    return `<circle cx="${x+w*.5}" cy="${y+h*.82}" r="${detail ? 6 : 2.4}" fill="#c7b28b"/>`;
  }
  if (opening === "pass-through") {
    return `<path d="M${x+w*.18} ${y+h*.94}H${x+w*.82}" stroke="#eeeae2" stroke-width="${detail ? 9 : 4}"/>`;
  }
  return "";
}

function topologyMarkup(module, x, y, w, h, color, opening, detail) {
  return (module.frontTopology?.elements || []).map(element => {
    const ex = x + element.x*w;
    const ey = y + element.y*h;
    const ew = element.width*w;
    const eh = element.height*h;
    let fill = finishColor(module, color);
    if (element.type === "niche") fill = "#f8f7f4";
    if (element.type === "appliance") fill = "#313438";
    const dash = element.type === "niche" ? ' stroke-dasharray="5 4"' : "";
    return `<g data-front-element="${element.type}">
      <rect x="${ex}" y="${ey}" width="${ew}" height="${eh}" rx="${detail ? 3 : 1.5}" fill="${fill}" stroke="#353535" stroke-width="${detail ? 2.5 : 1.4}"${dash}/>
      ${element.type === "appliance" ? `<rect x="${ex+ew*.12}" y="${ey+eh*.18}" width="${ew*.76}" height="${eh*.65}" rx="3" fill="#17191b" stroke="#73777a" stroke-width="${detail ? 2 : 1}"/>` : ""}
      ${openingDecoration(module, element, opening, ex, ey, ew, eh, detail)}
    </g>`;
  }).join("");
}

export function moduleSvg(module, { detail = false, color = "#918981", opening = null } = {}) {
  const width = detail ? 520 : 160;
  const height = detail ? 330 : 112;
  if (module.placementClass === "feature") {
    return `<svg viewBox="0 0 ${width} ${height}" aria-hidden="true">
      <rect width="${width}" height="${height}" fill="#eeeae2"/>
      <path d="M${width*.12} ${height*.5}H${width*.88}" stroke="#d6a83b" stroke-width="${detail ? 18 : 7}" stroke-linecap="round"/>
      <path d="M${width*.17} ${height*.58}H${width*.83}" stroke="#ffe078" stroke-width="${detail ? 10 : 4}" opacity=".85"/>
    </svg>`;
  }
  const x = width*.12, y = height*.12, w = width*.76, h = height*.76;
  return `<svg viewBox="0 0 ${width} ${height}" aria-hidden="true">
    <rect width="${width}" height="${height}" fill="#eeeae2"/>
    <rect x="${x-width*.035}" y="${y-height*.035}" width="${w+width*.07}" height="${h+height*.07}" rx="4" fill="#f6f4ef" stroke="#68645e" stroke-width="3"/>
    ${topologyMarkup(module,x,y,w,h,color,opening,detail)}
  </svg>`;
}

function appendTopology(group, module, placement, color) {
  const {x,y,width,height} = placement.sceneRect;
  for (const element of module.frontTopology?.elements || []) {
    const ex=x+element.x*width, ey=y+element.y*height, ew=element.width*width, eh=element.height*height;
    let fill=finishColor(module,color);
    if (element.type==="niche") fill="#f8f7f4";
    if (element.type==="appliance") fill="#292c30";
    const rect=svg("rect",{x:ex,y:ey,width:ew,height:eh,rx:2,fill,stroke:"#1f2022","stroke-width":2});
    if (element.type==="niche") rect.setAttribute("stroke-dasharray","5 4");
    group.append(rect);
    if (element.type==="appliance") {
      group.append(svg("rect",{x:ex+ew*.12,y:ey+eh*.17,width:ew*.76,height:eh*.66,rx:3,fill:"#111315",stroke:"#76797c","stroke-width":2}));
    }
  }
}

function appendFreestandingStove(sceneModules, fallback) {
  const {x,y,width,height}=fallback.sceneRect;
  const group=svg("g",{"data-fallback-id":"freestanding-stove"});
  group.classList.add("scene-module","is-enabled","scene-fallback");
  group.append(
    svg("rect",{x,y,width,height,rx:5,fill:"#d7d9da",stroke:"#343638","stroke-width":3}),
    svg("rect",{x:x+width*.04,y:y+height*.02,width:width*.92,height:height*.12,rx:3,fill:"#292c2f"}),
    svg("rect",{x:x+width*.12,y:y+height*.28,width:width*.76,height:height*.48,rx:4,fill:"#151719",stroke:"#666","stroke-width":2}),
    svg("line",{x1:x+width*.25,y1:y+height*.22,x2:x+width*.75,y2:y+height*.22,stroke:"#666","stroke-width":5,"stroke-linecap":"round"})
  );
  sceneModules.append(group);
}

export function renderScene({
  sceneModules, sceneHitAreas, sceneEmpty, orderedModules, placementById,
  enabledIds, selectedId, lastEnabledId, color, layout, onSelect
}) {
  sceneModules.replaceChildren();
  sceneHitAreas.replaceChildren();
  const enabled=new Set(enabledIds);

  const legacyOven=document.querySelector(".appliance-oven");
  if (legacyOven) legacyOven.style.visibility="hidden";

  const fallback=layout.fallbacks?.find(item=>item.id==="freestanding-stove");
  if (fallback && !enabled.has("lower-stove")) appendFreestandingStove(sceneModules,fallback);

  for (const module of orderedModules) {
    const placement=placementById.get(module.id);
    if (!placement) continue;
    const active=enabled.has(module.id);
    const selected=selectedId===module.id;
    const last=lastEnabledId===module.id && active;
    const {x,y,width,height}=placement.sceneRect;

    const group=svg("g",{"data-module-id":module.id});
    group.classList.add("scene-module");
    group.classList.toggle("is-enabled",active);
    group.classList.toggle("is-selected",selected);
    if (module.placementClass==="feature") {
      group.append(svg("rect",{x,y,width,height,rx:12,fill:"#ffd766",opacity:.76}));
    } else {
      group.append(svg("rect",{x,y,width,height,rx:4,fill:"#f6f4ef",stroke:"#1f2022","stroke-width":3}));
      appendTopology(group,module,placement,color);
    }
    sceneModules.append(group);

    const hit=svg("rect",{x,y,width,height,rx:5,tabindex:active?0:-1});
    hit.classList.add("scene-hit");
    hit.classList.toggle("is-enabled",active);
    hit.classList.toggle("is-selected",selected);
    hit.classList.toggle("is-last-enabled",last);
    hit.dataset.moduleId=module.id;
    hit.setAttribute("aria-label",module.name);
    hit.addEventListener("click",()=>onSelect(module.id));
    hit.addEventListener("keydown",event=>{
      if(event.key==="Enter"||event.key===" "){event.preventDefault();onSelect(module.id);}
    });
    sceneHitAreas.append(hit);
  }

  sceneEmpty.classList.add("is-hidden");
}

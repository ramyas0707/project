import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Sparkles, FolderTree, FileCode2, Download, Github, Upload, ShieldCheck, ChevronRight, CheckCircle2, AlertCircle, LoaderCircle, Rocket, FileText, RefreshCw, ExternalLink, LockKeyhole, Code2 } from 'lucide-react';
import './styles.css';

const API = '/api';
async function api(path, options={}) {
  const res = await fetch(API+path, {credentials:'include', ...options});
  const data = await res.json().catch(()=>({detail:'Unexpected server response'}));
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return data;
}
function App(){
  const [topic,setTopic]=useState('Knowledge Graph-Enhanced Recommendation Engine Using Graph Embeddings and Collaborative Filtering');
  const [language,setLanguage]=useState('Python');
  const [framework,setFramework]=useState('FastAPI');
  const [file,setFile]=useState(null);
  const [project,setProject]=useState(null);
  const [files,setFiles]=useState([]);
  const [selected,setSelected]=useState('');
  const [busy,setBusy]=useState('');
  const [notice,setNotice]=useState(null);
  const [health,setHealth]=useState(null);
  const [repos,setRepos]=useState([]);
  const [repo,setRepo]=useState('');
  const [repoName,setRepoName]=useState('knowledge-graph-recommender');
  const [description,setDescription]=useState('Knowledge graph-enhanced recommendation engine');
  const [visibility,setVisibility]=useState('private');
  const [branch,setBranch]=useState('main');
  const [createNew,setCreateNew]=useState(true);
  const [overwrite,setOverwrite]=useState(false);
  const [showConfirm,setShowConfirm]=useState(false);
  useEffect(()=>{api('/health').then(setHealth).catch(()=>setHealth({status:'offline'}));
    const q=new URLSearchParams(location.search);
    if(q.get('github_connected')) {setNotice({type:'success',text:'GitHub connected successfully.'}); history.replaceState({},'',location.pathname);}
    if(q.get('github_error')) {setNotice({type:'error',text:'GitHub authorization did not complete. Please try again.'}); history.replaceState({},'',location.pathname);}
  },[]);
  const selectedFile=files.find(f=>f.path===selected);
  const folders=useMemo(()=>files.map(f=>f.path.split('/').slice(0,-1).join('/')).filter(Boolean),[files]);
  async function generate(){
    setBusy('generate');setNotice(null);
    try{
      let spec=topic;
      if(file){const fd=new FormData();fd.append('topic',topic);fd.append('file',file);const a=await api('/projects/analyze',{method:'POST',body:fd});spec=a.topic;}
      const p=await api('/projects/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({topic:spec,language,framework})});
      setProject(p); const d=await api(`/projects/${p.project_id}/files`);setFiles(d.files);setSelected(d.files[0]?.path||'');
      setNotice({type:p.mode==='ai'?'success':'info',text:p.message});
    }catch(e){setNotice({type:'error',text:e.message});}finally{setBusy('');}
  }
  async function connectGitHub(){
    try{setBusy('github');const r=await fetch(API+'/github/login',{credentials:'include',redirect:'manual'});
      // Redirects may be opaque in browsers; direct navigation lets GitHub OAuth proceed.
      if(r.type==='opaqueredirect'||r.status===0){location.href=API+'/github/login';return;}
      if(r.redirected){location.href=r.url;return;}
      const d=await r.json().catch(()=>({detail:'Could not start GitHub login'}));throw new Error(d.detail||'Could not start GitHub login');
    }catch(e){setNotice({type:'error',text:e.message});setBusy('');}
  }
  async function loadRepos(){
    setBusy('repos');try{const d=await api('/github/repositories');setRepos(d.repositories);setNotice({type:'success',text:`Loaded ${d.repositories.length} repositories.`});}
    catch(e){setNotice({type:'error',text:e.message});}finally{setBusy('');}
  }
  async function publish(){
    setBusy('publish');setShowConfirm(false);setNotice(null);
    try{const d=await api('/github/publish',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project_id:project.project_id,repository:createNew?repoName:repo,description,visibility,branch,create_new:createNew,confirm:true,overwrite})});
      setNotice({type:'success',text:`Published ${d.files_published} files to ${d.repository_url}`});window.open(d.repository_url,'_blank','noopener,noreferrer');
    }catch(e){setNotice({type:'error',text:e.message});}finally{setBusy('');}
  }
  return <div className="app-shell">
    <aside className="sidebar"><div className="brand"><div className="brand-icon"><Sparkles size={21}/></div><div><strong>AI Project Builder</strong><small>BUILD • SHIP • REPEAT</small></div></div>
      <div className="nav-label">WORKSPACE</div><div className="nav-item active"><Code2 size={17}/> Project Studio</div><div className="nav-item"><FolderTree size={17}/> File Explorer</div><div className="nav-item"><Github size={17}/> GitHub Publisher</div>
      <div className="side-bottom"><div className="secure-icon"><ShieldCheck size={18}/></div><strong>Secure by design</strong><p>AI keys stay on the backend. GitHub access requires authorization.</p><span className="status-dot"/> API {health?.status==='ok'?'connected':'checking'}</div>
    </aside>
    <main className="main">
      <header className="topbar"><div><div className="eyebrow">YOUR AI DEVELOPMENT WORKSPACE</div><h1>Turn ideas into <span>working code.</span></h1><p>Describe your project. Generate a codebase. Download it or publish to GitHub.</p></div><div className="top-badge"><span className="pulse"/> {health?.ai_configured?'AI provider configured':'AI setup needed'}</div></header>
      {notice&&<div className={`notice ${notice.type}`}><div>{notice.type==='error'?<AlertCircle size={18}/>:<CheckCircle2 size={18}/>}</div><span>{notice.text}</span><button onClick={()=>setNotice(null)} aria-label="Dismiss">×</button></div>}
      <section className="steps"><div className="step done"><span>1</span><div><b>Describe</b><small>Define your idea</small></div></div><ChevronRight/><div className={`step ${project?'done':'current'}`}><span>2</span><div><b>Generate</b><small>Build source files</small></div></div><ChevronRight/><div className="step"><span>3</span><div><b>Publish</b><small>Download or GitHub</small></div></div></section>
      <div className="content-grid">
        <section className="panel input-panel"><div className="panel-heading"><div className="panel-icon purple"><Sparkles size={19}/></div><div><h2>Project specification</h2><p>Give the builder enough detail to create a useful MVP.</p></div></div>
          <label htmlFor="topic">PROJECT TOPIC & REQUIREMENTS</label><textarea id="topic" value={topic} onChange={e=>setTopic(e.target.value)} placeholder="Describe what your application should do..." rows={7}/>
          <div className="upload-zone"><input id="spec-file" type="file" accept=".pdf,.docx,.txt,.png,.jpg,.jpeg,.webp" onChange={e=>setFile(e.target.files?.[0]||null)}/><label htmlFor="spec-file" className="upload-content"><div className="upload-icon"><Upload size={19}/></div><div><b>{file?file.name:'Upload project brief'}</b><small>{file?'File selected · click to replace':'PDF, DOCX, TXT or image · max 8 MB'}</small></div><span className="browse">Browse</span></label></div>
          <div className="two-fields"><div><label htmlFor="language">LANGUAGE</label><select id="language" value={language} onChange={e=>setLanguage(e.target.value)}><option>Python</option><option>JavaScript</option><option>TypeScript</option><option>Java</option><option>C#</option><option>Go</option></select></div><div><label htmlFor="framework">FRAMEWORK / STACK</label><select id="framework" value={framework} onChange={e=>setFramework(e.target.value)}><option>FastAPI</option><option>Flask</option><option>Django</option><option>React + Vite</option><option>Node.js + Express</option><option>Spring Boot</option><option>Standalone / CLI</option></select></div></div>
          <button className="primary-btn" onClick={generate} disabled={!!busy||topic.trim().length<3}>{busy==='generate'?<><LoaderCircle className="spin" size={18}/> Generating project...</>:<><Sparkles size={18}/> Generate project <span>→</span></>}</button>
          <div className="tiny-safe"><LockKeyhole size={13}/> Your specification is sent only to this app's backend and configured AI provider.</div>
        </section>
        <section className="panel output-panel"><div className="panel-heading"><div className="panel-icon blue"><FolderTree size={19}/></div><div><h2>Generated codebase</h2><p>{project?`${files.length} files ready to review`:'Your project files will appear here'}</p></div><div className={`status-pill ${project?'ready':''}`}>{project?'READY':'WAITING'}</div></div>
          {!project?<div className="empty-state"><div className="empty-art"><div className="art-window"><div/><div/><div/><section><Code2 size={35}/></section></div><Sparkles className="sparkle s1"/><Sparkles className="sparkle s2"/></div><h3>Your codebase starts here</h3><p>Enter a project idea and click Generate Project. Files will appear in an explorable tree with a code preview.</p><div className="empty-chips"><span><FileCode2 size={13}/> Source files</span><span><FileText size={13}/> README</span><span><ShieldCheck size={13}/> Safe export</span></div></div>
          :<><div className="file-layout"><div className="file-list"><div className="file-list-title">EXPLORER <span>{files.length}</span></div>{files.map(f=><button key={f.path} className={`file-row ${selected===f.path?'selected':''}`} onClick={()=>setSelected(f.path)}><FileCode2 size={14}/><span>{f.path}</span></button>)}</div><div className="code-view"><div className="code-toolbar"><span><span className="file-dot"/> {selected||'Select a file'}</span><button onClick={()=>selectedFile&&navigator.clipboard.writeText(selectedFile.content)} disabled={!selectedFile}>Copy</button></div><pre>{selectedFile?.content||'Select a file from the explorer.'}</pre></div></div>
            <div className="export-row"><div><b>Ready to take it further?</b><small>Download your code or publish it to a repository.</small></div><a className="secondary-btn" href={project?`${API}/projects/${project.project_id}/download`:undefined} onClick={e=>{if(!project)e.preventDefault()}}><Download size={16}/> Download ZIP</a></div></>}
        </section>
      </div>
      <section className="panel github-panel"><div className="panel-heading"><div className="panel-icon dark"><Github size={20}/></div><div><h2>Publish to GitHub</h2><p>Authorize securely, review your target, then commit the generated files.</p></div><div className="github-mark"><Github size={25}/></div></div>
        <div className="github-actions"><div className="github-intro"><div className="gh-check"><ShieldCheck size={20}/></div><div><b>Connect your GitHub account</b><p>OAuth authorization. No password or personal access token is requested by this app.</p></div></div><div className="button-stack"><button className="github-btn" onClick={connectGitHub} disabled={!!busy}>{busy==='github'?<LoaderCircle className="spin" size={17}/>:<Github size={17}/>} Connect GitHub</button><button className="text-btn" onClick={loadRepos} disabled={!!busy}><RefreshCw size={14}/> Load repositories</button></div></div>
        <div className="publish-form"><div className="form-title">PUBLISH SETTINGS <span>Step 2 of 2</span></div><div className="radio-line"><label><input type="radio" checked={createNew} onChange={()=>setCreateNew(true)}/> Create new repository</label><label><input type="radio" checked={!createNew} onChange={()=>setCreateNew(false)}/> Use existing repository</label></div>
          {createNew?<div className="two-fields"><div><label>REPOSITORY NAME</label><input value={repoName} onChange={e=>setRepoName(e.target.value)} placeholder="my-project"/></div><div><label>DESCRIPTION</label><input value={description} onChange={e=>setDescription(e.target.value)} placeholder="Short project description"/></div></div>:<div className="two-fields"><div><label>EXISTING REPOSITORY</label><select value={repo} onChange={e=>setRepo(e.target.value)}><option value="">Choose a repository...</option>{repos.map(r=><option key={r.full_name} value={r.full_name}>{r.full_name}{r.private?' · private':''}</option>)}</select></div><div><label>TARGET BRANCH</label><input value={branch} onChange={e=>setBranch(e.target.value)}/></div></div>}
          {createNew&&<div className="two-fields"><div><label>VISIBILITY</label><select value={visibility} onChange={e=>setVisibility(e.target.value)}><option value="private">Private — only you and collaborators</option><option value="public">Public — visible to everyone</option></select></div><div><label>INITIAL BRANCH</label><input value={branch} onChange={e=>setBranch(e.target.value)}/></div></div>}
          <label className="check-row"><input type="checkbox" checked={overwrite} onChange={e=>setOverwrite(e.target.checked)}/> I understand publishing may add or update files in the target repository.</label>
          <button className="publish-btn" disabled={!project||!!busy||(!createNew&&!repo)||!overwrite} onClick={()=>setShowConfirm(true)}><Rocket size={17}/> Review & publish files</button>
          {!project&&<small className="hint">Generate a project first to enable publishing.</small>}
        </div>
      </section>
      <footer><span>AI PROJECT BUILDER</span><span><ShieldCheck size={13}/> Secure workflow · Review before publishing</span></footer>
    </main>
    {showConfirm&&<div className="modal-backdrop"><div className="modal"><div className="modal-icon"><Rocket size={22}/></div><h2>Confirm GitHub publishing</h2><p>You are about to publish <b>{files.length} files</b> to <b>{createNew?repoName:repo}</b> on branch <b>{branch}</b>. Review the file list above. Existing repository content may be updated by this commit.</p><div className="modal-actions"><button className="secondary-btn" onClick={()=>setShowConfirm(false)}>Go back</button><button className="publish-btn" onClick={publish}><Rocket size={16}/> Confirm & publish</button></div></div></div>}
  </div>
}
createRoot(document.getElementById('root')).render(<App/>);

'use strict';
// A focused workspace over the existing, tested capture and generation controls.
const workspaceTitle=document.createElement('div');workspaceTitle.className='workspace-title';workspaceTitle.innerHTML='<div><h1>Your persona studio</h1><p>Upload. Preview. Create.</p></div>';
document.querySelector('main').prepend(workspaceTitle);
const readiness=document.createElement('div');readiness.className='readiness';document.querySelector('.profile-bar').after(readiness);
const guide=document.createElement('div');guide.className='workspace-guide';guide.innerHTML='<strong>Start here:</strong> Create a persona → upload a clear photo or face video → add your voice → enter your script in Create. Preview speech before rendering.';readiness.after(guide);
const previousWorkspaceProfile=renderProfile;
renderProfile=function(){previousWorkspaceProfile();const p=profiles.find(p=>p.id===current);readiness.replaceChildren();for(const [name,ready]of [['Persona',!!p],['Face reference',!!p?.portrait||!!p?.samples?.face],['Normal voice',!!p?.samples?.['voice-normal']]]){const tag=document.createElement('span');tag.textContent=(ready?'✓ ':'○ ')+name;tag.className=ready?'':'missing';readiness.append(tag);}const hasVoice=p?.samples?.['voice-'+$('#generation-tone').value];$('#preview-voice').disabled=!hasVoice;$('#generate').disabled=!hasVoice||!(p?.portrait||p?.samples?.face);};
const rename=document.createElement('button');rename.className='secondary';rename.textContent='Rename';$('#new-profile').after(rename);rename.onclick=safeAction(async()=>{if(!current)throw Error('Create a persona first');const p=profiles.find(p=>p.id===current);const name=prompt('Persona name',p.name);if(name===null)return;await api('/api/rename-profile',{id:current,name});await loadProfiles();});
$('#generation-tone').onchange=()=>renderProfile();
const note=document.createElement('p');note.className='hint';note.textContent='Photo input animates a still portrait. Video input supplies a portrait frame. Neither learns your full body or exact gestures. For best facial detail, choose a clear head-and-shoulders image.';$('.portrait-tools').after(note);
// Use retained sources explicitly; importing a photo no longer hides how to switch back.
const sourceButtons=document.createElement('div');sourceButtons.className='compact-actions';for(const [source,label]of [['photo','Use uploaded photo'],['video','Use video portrait']]){const button=document.createElement('button');button.className='secondary';button.textContent=label;button.onclick=safeAction(async()=>{await api('/api/face-source',{profile:current,source});await loadProfiles();});sourceButtons.append(button);}$('.portrait-tools').after(sourceButtons);
const originalStudioSubmit=submitStudioJob;
submitStudioJob=async function(kind){try{await originalStudioSubmit(kind);}finally{renderProfile();}};
renderProfile();
$('#composition').insertAdjacentHTML('afterend','<label for="quality" style="margin-top:18px">FACE RENDERING</label><select id="quality"><option value="draft">Draft · 256 pixels · lower memory</option><option value="detail">Detail · 512 pixels · slower, more memory</option></select><p class="hint">Detail mode uses a higher-resolution face model. Sharp, close-up source images matter most. GPU memory failures retry on CPU.</p>');
submitStudioJob=async function(kind){$('#generate').disabled=true;$('#preview-voice').disabled=true;try{job=await api('/api/generate',{profile:current,tone:$('#generation-tone').value,script:$('#script').value,kind,speed:Number($('#speed').value),expression:Number($('#expression').value),composition:$('#composition').value,quality:$('#quality').value,pronunciations:$('#pronunciations').value});$('#job-log').hidden=true;renderJob();await refreshJobs();}finally{renderProfile();}};
// Keep the upload workflow prominent; camera capture is an optional section.
const faceCard=$('#camera').closest('.card');
const cameraDetails=document.createElement('details');cameraDetails.className='camera-section';cameraDetails.innerHTML='<summary>Or record a new camera reference</summary>';
const cameraPreview=$('.preview'),cameraHint=cameraPreview.nextElementSibling,cameraActions=cameraHint.nextElementSibling,cameraState=$('#face-state');
cameraDetails.append(cameraPreview,cameraHint,cameraActions,cameraState);
faceCard.querySelector('.card-heading').after($('.portrait-tools'));
faceCard.append(cameraDetails);

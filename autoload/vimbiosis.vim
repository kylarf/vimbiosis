function! vimbiosis#start_bridge() abort
  if exists('g:vimbiosis_job') && job_status(g:vimbiosis_job) ==# 'run'
    return
  endif
  let s:root = fnamemodify(expand('<script>:p'), ':h:h')
  let s:socket = tempname() . '.sock'
  let s:token = printf('%x-%x-%s', localtime(), getpid(), fnamemodify(tempname(), ':t'))
  let l:cmd = [s:root . '/bin/vimbiosis', 'bridge', '--socket', s:socket, '--token', s:token]
  let g:vimbiosis_job = job_start(l:cmd, {
        \ 'in_mode': 'json', 'out_mode': 'json', 'err_mode': 'nl',
        \ 'out_cb': function('s:message'), 'close_cb': function('s:closed')})
  if job_status(g:vimbiosis_job) !=# 'run'
    throw 'vimbiosis: failed to start bridge'
  endif
  let g:vimbiosis_socket = s:socket
  let g:vimbiosis_token = s:token
  let g:vimbiosis_root = s:root
endfunction

function! s:message(channel, message) abort
  let l:m = a:message
  if type(l:m) != v:t_dict || !has_key(l:m, 'id') || !has_key(l:m, 'request')
    return
  endif
  try
    let l:result = vimbiosis#dispatch(l:m.request)
  catch
    let l:result = {'ok': v:false, 'error': v:exception}
  endtry
  call ch_sendexpr(a:channel, {'reply_to': l:m.id, 'result': l:result})
endfunction

function! s:closed(channel) abort
  unlet! g:vimbiosis_job
endfunction

function! vimbiosis#dispatch(request) abort
  let l:op = get(a:request, 'op', '')
  if l:op ==# 'status'
    return {'ok': v:true, 'attached': exists('$VIMBIOSIS_SESSION') && !empty($VIMBIOSIS_SESSION)}
  elseif l:op ==# 'buffers'
    let l:items = []
    for l:b in getbufinfo({'buflisted': 1})
      if empty(l:b.name) | continue | endif
      let l:windows = []
      for l:w in getwininfo()
        if l:w.bufnr == l:b.bufnr | call add(l:windows, {'tab': l:w.tabnr, 'winid': l:w.winid}) | endif
      endfor
      call add(l:items, {'bufnr': l:b.bufnr, 'path': fnamemodify(l:b.name, ':p'),
            \ 'loaded': l:b.loaded, 'modified': l:b.changed, 'changedtick': l:b.changedtick,
            \ 'windows': l:windows})
    endfor
    return {'ok': v:true, 'buffers': l:items}
  elseif l:op ==# 'read-buffer'
    let l:path = fnamemodify(get(a:request, 'path', ''), ':p')
    let l:buf = bufnr(l:path)
    if l:buf < 0 | return {'ok': v:false, 'error': 'buffer not found', 'path': l:path} | endif
    let l:lines = getbufline(l:buf, max([1, get(a:request, 'start', 1)]), get(a:request, 'end', '$'))
    return {'ok': v:true, 'path': l:path, 'changedtick': getbufvar(l:buf, 'changedtick'), 'lines': l:lines}
  elseif l:op ==# 'open'
    return vimbiosis#open(a:request)
  elseif l:op ==# 'notify'
    for l:file in get(a:request, 'files', []) | call vimbiosis#refresh(l:file) | endfor
    return {'ok': v:true}
  endif
  return {'ok': v:false, 'error': 'unknown operation'}
endfunction

function! vimbiosis#open(request) abort
  let l:path = fnamemodify(get(a:request, 'path', ''), ':p')
  let l:existing = bufnr(l:path)
  let l:win = -1
  if l:existing >= 0
    for l:w in getwininfo()
      if l:w.bufnr == l:existing | let l:win = l:w.winid | break | endif
    endfor
  endif
  if l:win > 0
    call win_gotoid(l:win)
  else
    if get(a:request, 'vertical', v:false) | vertical split | else | split | endif
    execute 'edit ' . fnameescape(l:path)
  endif
  call cursor(max([1, get(a:request, 'line', 1)]), max([1, get(a:request, 'column', 1)]))
  normal! zt
  return {'ok': v:true, 'path': l:path, 'line': line('.')}
endfunction

function! vimbiosis#refresh(file) abort
  let l:path = fnamemodify(a:file, ':p')
  let l:buf = bufnr(l:path)
  if l:buf >= 0 && getbufvar(l:buf, '&modified')
    let g:vimbiosis_conflict = l:path
    echohl WarningMsg | echomsg 'Vimbiosis: unsaved changes; skipped ' . l:path | echohl None
    return
  endif
  let l:wins = getwininfo()
  let l:current = win_getid()
  if l:buf < 0
    let l:buf = bufadd(l:path)
  endif
  call bufload(l:buf)
  if !exists('g:vimbiosis_live_win') || win_id2win(g:vimbiosis_live_win) == 0
    let g:vimbiosis_anchor = l:current
    let l:wide = winwidth(0) * 2 >= winheight(0)
    if l:wide | vertical split | else | split | endif
    let g:vimbiosis_live_win = win_getid()
  endif
  call win_execute(g:vimbiosis_live_win, 'execute "buffer " . ' . l:buf)
  call win_gotoid(l:current)
  return
endfunction


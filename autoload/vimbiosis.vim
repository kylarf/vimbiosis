let s:requests = []
let s:pump = -1
let s:draining = 0

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
  if s:pump != -1
    call timer_stop(s:pump)
  endif
  let s:requests = []
  let s:pump = timer_start(50, function('s:drain'), {'repeat': -1})
endfunction

function! s:trace(event, message) abort
  if !exists('g:vimbiosis_trace')
    let g:vimbiosis_trace = []
  endif
  call add(g:vimbiosis_trace, {'event': a:event, 'id': a:message.id,
        \ 'operation': get(a:message.request, 'op', ''),
        \ 'time': reltimefloat(reltime()), 'mode': mode(1)})
  if len(g:vimbiosis_trace) > 64
    call remove(g:vimbiosis_trace, 0)
  endif
endfunction

function! s:message(channel, message) abort
  let l:m = a:message
  if type(l:m) != v:t_dict || !has_key(l:m, 'id') || !has_key(l:m, 'request')
    return
  endif
  call s:trace('queued', l:m)
  call add(s:requests, [a:channel, l:m])
endfunction

function! s:drain(timer) abort
  if s:draining || empty(s:requests)
    return
  endif
  let s:draining = 1
  try
    let l:item = remove(s:requests, 0)
    call s:execute(l:item[0], l:item[1])
  finally
    let s:draining = 0
  endtry
endfunction

function! s:execute(channel, message) abort
  let l:m = a:message
  call s:trace('started', l:m)
  try
    if get(l:m.request, 'op', '') ==# 'notify'
      silent let l:result = vimbiosis#dispatch(l:m.request)
      redraw
    else
      let l:result = vimbiosis#dispatch(l:m.request)
    endif
  catch
    let l:result = {'ok': v:false, 'error': v:exception}
  endtry
  call ch_sendexpr(a:channel, {'reply_to': l:m.id, 'result': l:result})
  call s:trace('replied', l:m)
endfunction

function! s:closed(channel) abort
  if exists('g:vimbiosis_job') && job_getchannel(g:vimbiosis_job) != a:channel
    return
  endif
  if s:pump != -1
    call timer_stop(s:pump)
    let s:pump = -1
  endif
  let s:requests = []
  unlet! g:vimbiosis_job
endfunction

function! vimbiosis#dispatch(request) abort
  let l:op = get(a:request, 'op', '')
  if l:op ==# 'before'
    let l:conflicts = []
    for l:path in get(a:request, 'files', [])
      let l:buf = bufnr(l:path)
      if l:buf >= 0 && getbufvar(l:buf, '&modified')
        call add(l:conflicts, {'path': l:path, 'bufnr': l:buf,
              \ 'changedtick': getbufvar(l:buf, 'changedtick')})
      endif
    endfor
    return {'ok': empty(l:conflicts), 'conflicts': l:conflicts}
  elseif l:op ==# 'status'
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
    let l:conflicts = []
    let l:changes = get(a:request, 'changes',
          \ map(copy(get(a:request, 'files', [])), '{"path": v:val, "hunks": []}'))
    let l:last = -1
    for l:index in range(len(l:changes))
      let l:change = l:changes[l:index]
      if !get(l:change, 'deleted', 0) && !getbufvar(bufnr(l:change.path), '&modified')
        let l:last = l:index
      endif
    endfor
    for l:index in range(len(l:changes))
      let l:change = l:changes[l:index]
      let l:buf = bufnr(l:change.path)
      if l:buf >= 0 && getbufvar(l:buf, '&modified')
        call add(l:conflicts, {'path': l:change.path, 'bufnr': l:buf,
              \ 'changedtick': getbufvar(l:buf, 'changedtick')})
        continue
      endif
      let l:window = get(l:change, 'deleted', 0) ? 0 :
            \ vimbiosis#refresh(l:change.path, l:index == l:last)
      call vimbiosis#changes#record(l:change, l:window)
    endfor
    call vimbiosis#changes#show_if_multiple()
    return {'ok': empty(l:conflicts), 'conflicts': l:conflicts}
  endif
  return {'ok': v:false, 'error': 'unknown operation'}
endfunction

function! s:split(vertical) abort
  call win_gotoid(get(g:, 'vimbiosis_anchor_win', win_getid()))
  let l:wide = winwidth(0) >= 2 * winheight(0)
  if a:vertical || l:wide
    belowright vertical split
  else
    aboveleft split
  endif
  return win_getid()
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
    call s:split(get(a:request, 'vertical', v:false))
    execute 'edit ' . fnameescape(l:path)
  endif
  call cursor(max([1, get(a:request, 'line', 1)]), max([1, get(a:request, 'column', 1)]))
  normal! zt
  return {'ok': v:true, 'path': l:path, 'line': line('.')}
endfunction

function! s:reload(window, buffer) abort
  let l:autoread = getbufvar(a:buffer, '&l:autoread')
  call setbufvar(a:buffer, '&autoread', 1)
  try
    call win_execute(a:window, 'silent keepalt buffer ' . a:buffer)
    call win_execute(a:window, 'silent keepalt edit')
  finally
    if bufexists(a:buffer)
      call setbufvar(a:buffer, '&autoread', l:autoread)
    endif
  endtry
endfunction

function! vimbiosis#refresh(file, ...) abort
  let l:path = fnamemodify(a:file, ':p')
  let l:buf = bufnr(l:path)
  if l:buf >= 0 && getbufvar(l:buf, '&modified')
    let g:vimbiosis_conflict = l:path
    echohl WarningMsg | echomsg 'Vimbiosis: unsaved changes; skipped ' . l:path | echohl None
    return
  endif
  let l:current = win_getid()
  if l:buf < 0
    let l:buf = bufadd(l:path)
  endif
  for l:win in getwininfo()
    if l:win.tabnr == tabpagenr() && l:win.bufnr == l:buf
      call s:reload(l:win.winid, l:buf)
      return l:win.winid
    endif
  endfor
  if !get(g:, 'vimbiosis_follow', 1) || !get(a:000, 0, 1)
    call setbufvar(l:buf, 'vimbiosis_pending_reload', 1)
    return 0
  endif
  call bufload(l:buf)
  call setbufvar(l:buf, 'vimbiosis_pending_reload', 0)
  if !exists('g:vimbiosis_live_win') || empty(getwininfo(g:vimbiosis_live_win))
    let g:vimbiosis_live_win = s:split(0)
  endif
  call s:reload(g:vimbiosis_live_win, l:buf)
  call win_gotoid(l:current)
  return g:vimbiosis_live_win
endfunction


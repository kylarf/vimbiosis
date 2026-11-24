let s:requests = []
let s:pump = -1
let s:draining = 0
let s:errors = []
let s:root = fnamemodify(expand('<sfile>:p'), ':h:h')

function! vimbiosis#start_bridge() abort
  if exists('g:vimbiosis_job') && job_status(g:vimbiosis_job) ==# 'run'
    if exists('g:vimbiosis_session')
      return
    endif
    throw 'vimbiosis: bridge is still starting'
  endif
  unlet! g:vimbiosis_session g:vimbiosis_session_id
  let s:errors = []
  let s:requests = []
  let l:cmd = ['python3', s:root . '/python/vimbiosis.py']
  " Let stdin close on Vim exit so the bridge can remove its session entry.
  let g:vimbiosis_job = job_start(l:cmd, {
        \ 'stoponexit': '',
        \ 'in_mode': 'json', 'out_mode': 'json', 'err_mode': 'nl',
        \ 'out_cb': function('s:message'), 'close_cb': function('s:closed'),
        \ 'err_cb': function('s:error')})
  let l:started = reltime()
  while !exists('g:vimbiosis_session') && exists('g:vimbiosis_job')
        \ && job_status(g:vimbiosis_job) ==# 'run'
        \ && reltimefloat(reltime(l:started)) < 5
    sleep 10m
  endwhile
  if !exists('g:vimbiosis_session')
    if exists('g:vimbiosis_job')
      call job_stop(g:vimbiosis_job)
    endif
    throw 'vimbiosis: bridge failed to become ready within five seconds'
          \ . (empty(s:errors) ? '' : ': ' . join(s:errors, ' '))
  endif
  let g:vimbiosis_root = s:root
  if s:pump != -1
    call timer_stop(s:pump)
  endif
  let s:requests = []
  let s:pump = timer_start(50, function('s:drain'), {'repeat': -1})
endfunction

function! s:error(channel, message) abort
  if exists('g:vimbiosis_job') && job_getchannel(g:vimbiosis_job) == a:channel
    call add(s:errors, a:message)
  endif
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
  if !exists('g:vimbiosis_job') || job_getchannel(g:vimbiosis_job) != a:channel
    return
  endif
  let l:m = a:message
  if type(l:m) != v:t_dict
    return
  endif
  if get(l:m, 'event', '') ==# 'ready'
        \ && get(l:m, 'session', '') =~# '^\d\+:[0-9a-f]\{64}$'
    let g:vimbiosis_session = l:m.session
    let g:vimbiosis_session_id = l:m.id
    return
  endif
  if !has_key(l:m, 'id') || !has_key(l:m, 'request')
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
    if localtime() >= get(l:m, 'deadline', 0) / 1000
      let l:result = {'ok': v:false, 'error': 'Vim request expired before dispatch'}
    elseif get(l:m.request, 'op', '') ==# 'notify'
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
  unlet! g:vimbiosis_job g:vimbiosis_session g:vimbiosis_session_id
endfunction

function! s:file_buffer(buffer) abort
  return a:buffer > 0 && buflisted(a:buffer) && !empty(bufname(a:buffer))
        \ && empty(getbufvar(a:buffer, '&buftype')) && getbufvar(a:buffer, '&modifiable')
endfunction

function! s:file_window(id) abort
  let l:window = getwininfo(a:id)
  return a:id > 0 && !empty(l:window) && s:file_buffer(l:window[0].bufnr)
endfunction

function! vimbiosis#remember_window() abort
  if s:file_buffer(bufnr('%'))
    let s:last_file_window = win_getid()
  endif
endfunction

function! s:workspace() abort
  let l:result = {'ok': v:true, 'cwd': getcwd(-1), 'buffers': []}
  let l:windows = getwininfo()
  let l:omitted = 0
  for l:buffer in getbufinfo({'buflisted': 1})
    if !s:file_buffer(l:buffer.bufnr) | continue | endif
    if len(l:result.buffers) >= 100
      let l:omitted += 1
      continue
    endif
    let l:ids = map(filter(copy(l:windows), 'v:val.bufnr == l:buffer.bufnr'), 'v:val.winid')
    call add(l:result.buffers, {'path': l:buffer.name, 'modified': l:buffer.changed,
          \ 'loaded': l:buffer.loaded, 'windows': l:ids})
  endfor
  let l:result.omitted = l:omitted
  if s:file_buffer(bufnr('%'))
    let l:result.active = {'path': expand('%:p'), 'winid': win_getid(),
          \ 'line': line('.'), 'column': col('.')}
    if index(['v', 'V', "\<C-V>"], mode()) >= 0
      let l:result.active.selection = {'mode': mode(),
            \ 'anchor': getpos('v')[1:2], 'cursor': [line('.'), col('.')]}
    endif
  endif
  return l:result
endfunction

function! s:action(request) abort
  if !get(g:, 'vimbiosis_allow_arbitrary_actions', 0)
    return {'ok': v:false, 'error': 'Arbitrary Vim actions are disabled'}
  endif
  let l:target = get(a:request, 'winid',
        \ s:file_window(win_getid()) ? win_getid() : get(s:, 'last_file_window', 0))
  if !s:file_window(l:target) || !win_gotoid(l:target)
    return {'ok': v:false, 'error': 'No eligible editing window'}
  endif
  if a:request.op ==# 'execute_ex'
    return {'ok': v:true, 'output': strcharpart(execute(a:request.command), 0, 16000)}
  endif
  if mode(1) !=# 'n'
    return {'ok': v:false, 'error': 'Mapped keys require Vim Normal mode'}
  endif
  let l:keys = substitute(a:request.keys, '<[[:alnum:]_-]\+>',
        \ '\=eval(''"\'' . submatch(0) . ''"'')', 'g')
  call feedkeys(l:keys, 'mxt')
  return {'ok': v:true}
endfunction

function! vimbiosis#dispatch(request) abort
  let l:op = get(a:request, 'op', '')
  if l:op ==# 'workspace'
    return s:workspace()
  elseif l:op ==# 'focus_window'
    let l:id = a:request.winid
    return s:file_window(l:id) && win_gotoid(l:id)
          \ ? {'ok': v:true, 'winid': l:id} : {'ok': v:false, 'error': 'File window not found'}
  elseif index(['execute_ex', 'send_keys'], l:op) >= 0
    return s:action(a:request)
  elseif l:op ==# 'before'
    let l:conflicts = []
    for l:path in get(a:request, 'files', [])
      let l:buf = bufnr(l:path)
      if l:buf >= 0 && getbufvar(l:buf, '&modified')
        call add(l:conflicts, {'path': l:path, 'bufnr': l:buf,
              \ 'changedtick': getbufvar(l:buf, 'changedtick')})
      endif
    endfor
    return {'ok': empty(l:conflicts), 'conflicts': l:conflicts}
  elseif l:op ==# 'read_buffer'
    let l:path = fnamemodify(get(a:request, 'path', ''), ':p')
    let l:buf = bufnr('^' . escape(l:path, '\.^$~[]*') . '$')
    if !s:file_buffer(l:buf) || !bufloaded(l:buf)
      return {'ok': v:false, 'error': 'Loaded file buffer not found', 'path': l:path}
    endif
    let l:start = get(a:request, 'start', 1)
    let l:end = min([get(a:request, 'end', l:start + 199), l:start + 199])
    let l:lines = []
    let l:remaining = 16000
    let l:truncated = l:end < min([get(a:request, 'end', 2147483647),
          \ getbufinfo(l:buf)[0].linecount])
    for l:line in getbufline(l:buf, l:start, l:end)
      call add(l:lines, strcharpart(l:line, 0, l:remaining))
      let l:remaining -= strchars(l:lines[-1]) + 1
      if l:remaining <= 0
        let l:truncated = v:true
        break
      endif
    endfor
    return {'ok': v:true, 'path': l:path, 'changedtick': getbufvar(l:buf, 'changedtick'),
          \ 'start': l:start, 'lines': l:lines, 'truncated': l:truncated}
  elseif l:op ==# 'open_file'
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

function! s:destination(vertical) abort
  let l:candidates = [win_getid(), get(g:, 'vimbiosis_anchor_win', 0)]
  call extend(l:candidates, map(getwininfo(), 'v:val.winid'))
  for l:id in l:candidates
    let l:info = getwininfo(l:id)
    if empty(l:info) || l:info[0].tabnr != tabpagenr() || get(l:info[0], 'popup', 0)
      continue
    endif
    let l:buf = l:info[0].bufnr
    if empty(bufname(l:buf)) && !getbufvar(l:buf, '&modified')
          \ && empty(getbufvar(l:buf, '&buftype'))
          \ && getbufline(l:buf, 1, '$') ==# ['']
      call win_gotoid(l:id)
      return l:id
    endif
  endfor
  return s:split(a:vertical)
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
  let l:existing = bufnr('^' . escape(l:path, '\.^$~[]*') . '$')
  let l:win = -1
  if l:existing >= 0
    for l:w in getwininfo()
      if l:w.bufnr == l:existing | let l:win = l:w.winid | break | endif
    endfor
  endif
  if l:win > 0
    call win_gotoid(l:win)
  else
    call s:destination(get(a:request, 'vertical', v:false))
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
    if get(t:, 'vimbiosis_review', 0)
      let l:origin = vimbiosis#changes#review_origin()
      if !l:origin || !win_gotoid(l:origin)
        call setbufvar(l:buf, 'vimbiosis_pending_reload', 1)
        return 0
      endif
    endif
    let g:vimbiosis_live_win = s:destination(0)
  endif
  call s:reload(g:vimbiosis_live_win, l:buf)
  call win_gotoid(l:current)
  return g:vimbiosis_live_win
endfunction


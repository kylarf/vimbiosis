function! vimbiosis#agent#start(args, mods) abort
  call vimbiosis#start_bridge()
  let l:parts = split(a:args)
  let l:agent = remove(l:parts, 0)
  if index(['codex', 'claude'], l:agent) < 0 | throw 'vimbiosis: agent must be codex or claude' | endif
  if l:agent ==# 'codex' && index(l:parts, '--no-daemon') < 0
    call insert(l:parts, '--no-daemon')
  endif
  let l:env = {
        \ 'VIMBIOSIS_SESSION': g:vimbiosis_session,
        \ 'PATH': g:vimbiosis_root . '/bin:' . $PATH}
  execute a:mods . ' new'
  let l:buf = term_start([l:agent] + l:parts, {
        \ 'curwin': 1, 'env': l:env, 'term_name': 'Vimbiosis: ' . l:agent})
  if l:buf == 0
    throw 'vimbiosis: failed to start agent terminal'
  endif
  let g:vimbiosis_anchor_win = win_getid()
endfunction

function! vimbiosis#agent#attach() abort
  call vimbiosis#start_bridge()
  let g:vimbiosis_anchor_win = win_getid()
  echomsg 'export VIMBIOSIS_SESSION=' . shellescape(g:vimbiosis_session)
        \ . "\nFor Codex, launch with --no-daemon: codex --no-daemon"
endfunction

function! vimbiosis#agent#status() abort
  call vimbiosis#start_bridge()
  echomsg 'Vimbiosis bridge running on 127.0.0.1:' . split(g:vimbiosis_session, ':')[0]
endfunction

function! vimbiosis#agent#detach() abort
  if exists('g:vimbiosis_job') | call job_stop(g:vimbiosis_job) | unlet g:vimbiosis_job | endif
  unlet! g:vimbiosis_live_win g:vimbiosis_session
endfunction

function! vimbiosis#agent#follow() abort
  let g:vimbiosis_follow = !get(g:, 'vimbiosis_follow', 1)
  echomsg 'Vimbiosis follow ' . (g:vimbiosis_follow ? 'enabled' : 'paused')
endfunction

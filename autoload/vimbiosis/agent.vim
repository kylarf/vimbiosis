function! vimbiosis#agent#start(args, mods) abort
  call vimbiosis#start_bridge()
  let l:parts = split(a:args)
  let l:agent = remove(l:parts, 0)
  if index(['codex', 'claude'], l:agent) < 0 | throw 'vimbiosis: agent must be codex or claude' | endif
  let l:env = {
        \ 'VIMBIOSIS_SESSION': g:vimbiosis_socket . ':' . g:vimbiosis_token,
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
  echomsg 'export VIMBIOSIS_SESSION=' . shellescape(g:vimbiosis_socket . ':' . g:vimbiosis_token)
endfunction

function! vimbiosis#agent#status() abort
  if !exists('g:vimbiosis_job') | call vimbiosis#start_bridge() | endif
  echomsg 'Vimbiosis bridge running: ' . g:vimbiosis_socket
endfunction

function! vimbiosis#agent#detach() abort
  if exists('g:vimbiosis_job') | call job_stop(g:vimbiosis_job) | unlet g:vimbiosis_job | endif
  unlet! g:vimbiosis_live_win g:vimbiosis_socket g:vimbiosis_token
endfunction

function! vimbiosis#agent#follow() abort
  let g:vimbiosis_follow = !get(g:, 'vimbiosis_follow', 1)
  echomsg 'Vimbiosis follow ' . (g:vimbiosis_follow ? 'enabled' : 'paused')
endfunction

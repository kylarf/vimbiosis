function! s:launch_args(agent) abort
  let l:url = 'http://127.0.0.1:' . split(g:vimbiosis_session, ':')[0] . '/mcp'
  if a:agent ==# 'codex'
    return ['-c', 'mcp_servers.vimbiosis.url=' . json_encode(l:url),
          \ '-c', 'mcp_servers.vimbiosis.bearer_token_env_var="VIMBIOSIS_MCP_BEARER"']
  endif
  return ['--mcp-config', json_encode({'mcpServers': {'vimbiosis': {
        \ 'type': 'http', 'url': l:url, 'alwaysLoad': v:true,
        \ 'headers': {'Authorization': 'Bearer ${VIMBIOSIS_MCP_BEARER}'}}}})]
endfunction

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
        \ 'VIMBIOSIS_MCP_BEARER': split(g:vimbiosis_session, ':')[1]}
  execute a:mods . ' new'
  let l:buf = term_start([l:agent] + s:launch_args(l:agent) + l:parts, {
        \ 'curwin': 1, 'env': l:env, 'term_name': 'Vimbiosis: ' . l:agent})
  if l:buf == 0
    throw 'vimbiosis: failed to start agent terminal'
  endif
  let g:vimbiosis_anchor_win = win_getid()
endfunction

function! vimbiosis#agent#attach() abort
  call vimbiosis#start_bridge()
  let g:vimbiosis_anchor_win = win_getid()
  echomsg 'Vimbiosis session ' . g:vimbiosis_session_id
        \ . ': use vimbiosis -s ' . g:vimbiosis_session_id . ' <agent> [args] in an external shell'
endfunction

function! vimbiosis#agent#status() abort
  call vimbiosis#start_bridge()
  echomsg 'Vimbiosis bridge running on 127.0.0.1:' . split(g:vimbiosis_session, ':')[0]
endfunction

function! vimbiosis#agent#detach() abort
  if exists('g:vimbiosis_job')
    call ch_close_in(job_getchannel(g:vimbiosis_job))
    unlet g:vimbiosis_job
  endif
  unlet! g:vimbiosis_live_win g:vimbiosis_session g:vimbiosis_session_id
endfunction

function! vimbiosis#agent#follow() abort
  let g:vimbiosis_follow = !get(g:, 'vimbiosis_follow', 1)
  echomsg 'Vimbiosis follow ' . (g:vimbiosis_follow ? 'enabled' : 'paused')
endfunction

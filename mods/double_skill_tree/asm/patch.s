.intel_syntax noprefix
/*
 * Source of the code caves used by the double_skill_tree mod (Nine Parchments v1.1.0, build 4722).
 * The assembled bytes are the "patched" value of the 0x1405203b0 entry in ../mod.json. They fill
 * unused space where the original total-XP function lived.
 * You only need this to change the patch. Build with GNU binutils:
 *
 *   as --64 -o patch.o patch.s
 *   ld -o patch.elf -Ttext=0x1405203b0 -e total \
 *      --defsym F_ADDR=0x1405201d0 --defsym TREE_RET=0x14051d320 \
 *      --defsym FMT1=0x14268ec88 --defsym FMT2=0x14268ed18 \
 *      --defsym STR_VIOLET=0x14267b7b4 --defsym STR_BLUE=0x14267b0d8 --defsym SPRINTF=0x14194fe30 \
 *      --defsym BAR_AFTER_FMT=0x1407fda70 --defsym BAR_BODY=0x1407fd9ea --defsym BAR_EXIT=0x1407fdb3b \
 *      --defsym MD_IDX=0x1432f4f20 --defsym MD_ERR=0x1405759a7 --defsym MD_BACK=0x1405759d6 patch.o
 *   objcopy -O binary -j .text patch.elf patch.bin     (then pad with 0xCC to 571 bytes)
 */
.text
/* ---- placed at 0x1405203b0: total XP to reach level N = float sum of F(1..N) ---- */
.globl total
total:
  push rbx
  push rsi
  push rdi
  sub rsp, 0x30
  movaps [rsp+0x20], xmm6
  mov rsi, rcx
  mov ebx, edx
  xorps xmm6, xmm6
  mov edi, 1
loop_:
  cmp edi, ebx
  ja done
  mov rcx, rsi
  mov edx, edi
  call F_ADDR
  mov eax, eax
  xorps xmm0, xmm0
  cvtsi2ss xmm0, rax
  addss xmm6, xmm0
  inc edi
  jmp loop_
done:
  cvttss2si rax, xmm6
  movaps xmm6, [rsp+0x20]
  add rsp, 0x30
  pop rdi
  pop rsi
  pop rbx
  ret
  .p2align 4, 0xcc
/* ---- cave: entry of F clamps level to 89 ---- */
.globl cave
cave:
  sub rsp, 0x28
  mov r8d, edx
  cmp r8d, 89
  jbe 1f
  mov r8d, 89
1:
  jmp F_ADDR+7
  .p2align 4, 0xcc
/* ---- cave2: tree builder stores per-perk max; double it unless max <= 1 ---- */
.globl cave2
cave2:
  mov eax, r14d
  cmp eax, 1
  jbe 2f
  add eax, eax
2:
  mov [rdi+0x1c], eax
  mov rbx, [rbp+0x77]
  jmp TREE_RET
  .p2align 4, 0xcc
/* ---- caveA: skill bar image choice. p<=5: progress_<c>0p. p>5: 1st pass <c>05, 2nd pass purple overlay of k=p-5 bars ---- */
.globl caveA
caveA:
  and rax, -4
  mov r8, r12
  cmovne r8, rax
  mov r9d, ebx
  lea rdx, [rip+FMT1]
  cmp ebx, 5
  jbe 9f
  mov eax, [rbp+0x4f8]
  cmp ebx, eax
  jne 3f
  mov r9d, 5
  jmp 9f
3:
  sub eax, 5
  cmp dword ptr [r8], 0x6c6f6976
  je 4f
  lea r8, [rip+STR_VIOLET]
  mov r9d, eax
  jmp 9f
4:
  mov r9, r8
  cmp eax, 3
  jbe 5f
  sub eax, 3
  lea r9, [rip+STR_BLUE]
5:
  mov [rsp+0x20], eax
  mov r8d, 3
  lea rdx, [rip+FMT2]
9:
  call SPRINTF
  jmp BAR_AFTER_FMT
  .p2align 4, 0xcc
/* ---- caveB: loop end. p>5 and 1st pass done -> run body once more with ebx=p+16 ---- */
.globl caveB
caveB:
  mov eax, [rbp+0x4f8]
  cmp eax, 5
  jbe 1f
  cmp ebx, eax
  jne 1f
  lea ebx, [rax+0x10]
  jmp BAR_BODY
1:
  jmp BAR_EXIT
  .p2align 4, 0xcc
/* ---- caveC: ManifestDarkness spawnAll, SpawnAmounts[points-1] with points 6..10 = list[last] + list[points-1-count] ---- */
.globl caveC
caveC:
  dec r8d
  mov eax, [rip+MD_IDX]
  add rcx, rax
  mov r9d, [rbx+rcx*4+8]
  lea eax, [r9+r9]
  cmp r8d, eax
  jae MD_ERR
  mov rcx, [rbx+rcx*4]
  and rcx, -4
  cmp r8d, r9d
  jae 1f
  mov edx, [rcx+r8*4]
  jmp MD_BACK
1:
  lea eax, [r9-1]
  mov edx, [rcx+rax*4]
  mov eax, r8d
  sub eax, r9d
  add edx, [rcx+rax*4]
  jmp MD_BACK

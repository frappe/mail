import { Node } from '@tiptap/core'

export const CustomParagraphExtension = Node.create({
	name: 'paragraph',
	priority: 1000,
	group: 'block',
	content: 'inline*',
	parseHTML: () => [{ tag: 'div' }, { tag: 'p' }],
	renderHTML: ({ HTMLAttributes }) => ['div', HTMLAttributes, 0],
})
